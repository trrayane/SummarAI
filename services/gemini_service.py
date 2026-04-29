"""
services/gemini_service.py
Point d'entrée unique pour TOUS les appels à l'API Gemini.

Rotation automatique des clés API :
  - Lit jusqu'à 5 clés depuis settings (GEMINI_API_KEYS ou GEMINI_API_KEY)
  - Quand ResourceExhausted (quota épuisé) → passe à la clé suivante
  - Tourne en round-robin ; lève RuntimeError si toutes les clés sont épuisées
"""

import asyncio
import hashlib
import logging
import threading
import time
from typing import AsyncGenerator, List, Optional

import google.generativeai as genai
import google.api_core.exceptions as google_exceptions

from config.settings import settings
from prompts.style_prompts import STYLE_PROMPTS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gestionnaire de rotation des clés API
# ---------------------------------------------------------------------------

class _KeyRotator:
    """
    Gère un pool de clés API Gemini avec rotation automatique.
    Thread-safe grâce à un threading.Lock.
    """

    def __init__(self, keys: List[str]) -> None:
        if not keys:
            raise RuntimeError(
                "Aucune clé API Gemini configurée. "
                "Définissez GEMINI_API_KEYS ou GEMINI_API_KEY dans votre .env"
            )
        self._keys: List[str] = keys
        self._index: int = 0
        self._lock = threading.Lock()
        logger.info("KeyRotator initialisé avec %d clé(s) API.", len(keys))

    @property
    def current_key(self) -> str:
        with self._lock:
            return self._keys[self._index]

    def rotate(self) -> Optional[str]:
        """
        Passe à la clé suivante.
        Retourne la nouvelle clé, ou None si on a fait le tour complet.
        """
        with self._lock:
            next_index = (self._index + 1) % len(self._keys)
            if next_index == 0 and len(self._keys) > 1:
                # On est revenus au début → toutes les clés épuisées
                logger.error("Toutes les clés API Gemini sont épuisées.")
                return None
            self._index = next_index
            new_key = self._keys[self._index]
            logger.warning(
                "Rotation vers la clé API #%d/%d.", self._index + 1, len(self._keys)
            )
            return new_key

    @property
    def total(self) -> int:
        return len(self._keys)


_key_rotator = _KeyRotator(settings.get_api_keys())

# Configure le SDK avec la première clé
genai.configure(api_key=_key_rotator.current_key)

_MODEL_NAME = settings.GEMINI_MODEL  # "gemini-2.5-flash"

_QA_SYSTEM_PROMPT = """
You are a precise document assistant. Your only job is to answer questions
based strictly on the document provided. Never add outside information.
Always reply in the same language as the question.
If the answer is not found in the document, say so clearly.
Answer in english
"""

_TITLE_PROMPT_TEMPLATE = (
    "Génère un titre très court (3 à 6 mots maximum) et informatif et en anglais seulement"
    "pour le texte suivant. "
    "Réponds UNIQUEMENT avec le titre, sans guillemets, "
    "sans ponctuation finale, sans explication.\n\n"
    "Texte : {text}"
)

# ---------------------------------------------------------------------------
# Cache mémoire avec TTL
# ---------------------------------------------------------------------------
_CACHE_TTL = 3600
_cache: dict[str, dict] = {}


def _cache_key(text: str, style: str) -> str:
    return hashlib.sha256(f"{style}::{text}".encode()).hexdigest()


def _cache_get(key: str) -> Optional[str]:
    entry = _cache.get(key)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        _cache.pop(key, None)
        return None
    logger.debug("Cache hit — clé %s…", key[:12])
    return entry["value"]


def _cache_set(key: str, value: str) -> None:
    _cache[key] = {"value": value, "expires_at": time.time() + _CACHE_TTL}
    now = time.time()
    expired = [k for k, v in _cache.items() if now > v["expires_at"]]
    for k in expired:
        _cache.pop(k, None)


# ---------------------------------------------------------------------------
# Modèles Gemini — recréés à chaque rotation de clé
# ---------------------------------------------------------------------------

class _Models:
    def __init__(self) -> None:
        self._rebuild()

    def _rebuild(self) -> None:
        """Reconstruit les modèles avec la clé courante."""
        self.summary = genai.GenerativeModel(
            model_name=_MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
        )
        self.qa = genai.GenerativeModel(
            model_name=_MODEL_NAME,
            system_instruction=_QA_SYSTEM_PROMPT,
        )
        self.title = genai.GenerativeModel(model_name=_MODEL_NAME)

    def rotate_and_rebuild(self) -> bool:
        """
        Effectue une rotation de clé et reconstruit les modèles.
        Retourne False si toutes les clés sont épuisées.
        """
        new_key = _key_rotator.rotate()
        if new_key is None:
            return False
        genai.configure(api_key=new_key)
        self._rebuild()
        logger.info("Modèles Gemini reconfigurés avec la nouvelle clé.")
        return True

    def default_config(self, **kwargs) -> genai.types.GenerationConfig:
        return genai.types.GenerationConfig(
            temperature=settings.GEMINI_TEMPERATURE,
            max_output_tokens=settings.GEMINI_MAX_TOKENS,
            **kwargs,
        )


_models = _Models()


# ---------------------------------------------------------------------------
# Helper de streaming async avec rotation de clés
# ---------------------------------------------------------------------------

def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, (
        google_exceptions.ServiceUnavailable,
        google_exceptions.DeadlineExceeded,
        google_exceptions.InternalServerError,
        google_exceptions.ResourceExhausted,
    ))


def _is_quota_exhausted(exc: Exception) -> bool:
    """Détermine si l'erreur est due à un quota épuisé (429 / ResourceExhausted)."""
    return isinstance(exc, google_exceptions.ResourceExhausted)


async def _stream_gemini(
    model_attr: str,          # 'summary' | 'qa' | 'title'
    prompt: str,
    gen_config: Optional[genai.types.GenerationConfig] = None,
    max_retries: int = 3,
) -> AsyncGenerator[str, None]:
    """
    Streame les tokens Gemini de façon 100% async.
    Rotation automatique de clé sur ResourceExhausted.
    Retry avec backoff exponentiel sur les autres erreurs transitoires.
    """
    loop = asyncio.get_running_loop()
    config = gen_config or _models.default_config()

    # Nombre max de tentatives = retries × nombre de clés disponibles
    total_attempts = max_retries * _key_rotator.total

    for attempt in range(1, total_attempts + 1):
        model: genai.GenerativeModel = getattr(_models, model_attr)
        token_queue: asyncio.Queue = asyncio.Queue()
        errors: list = []

        def _run():
            try:
                for chunk in model.generate_content(prompt, stream=True, generation_config=config):
                    try:
                        t = chunk.text
                        if t:
                            loop.call_soon_threadsafe(token_queue.put_nowait, t)
                    except (ValueError, AttributeError):
                        pass
            except Exception as exc:
                errors.append(exc)
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, None)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        while True:
            token = await token_queue.get()
            if token is None:
                break
            yield token

        thread.join(timeout=10)

        if errors:
            exc = errors[0]

            # ── Quota épuisé → rotation immédiate, pas de sleep
            if _is_quota_exhausted(exc):
                logger.warning(
                    "Quota épuisé sur la clé #%d (tentative %d). Rotation…",
                    _key_rotator._index + 1, attempt,
                )
                rotated = _models.rotate_and_rebuild()
                if not rotated:
                    raise RuntimeError(
                        "Toutes les clés API Gemini ont atteint leur quota."
                    ) from exc
                continue  # réessai immédiat avec la nouvelle clé

            # ── Autre erreur transitoire → backoff exponentiel
            if _is_retryable(exc) and attempt < total_attempts:
                wait = 2 ** min(attempt, 5)
                logger.warning(
                    "Gemini retry %d/%d dans %ds : %s", attempt, total_attempts, wait, exc
                )
                await asyncio.sleep(wait)
                continue

            logger.error("Gemini erreur définitive : %s", exc)
            raise RuntimeError(f"Erreur Gemini API : {exc}") from exc

        return  # succès

    raise RuntimeError("Gemini API indisponible après plusieurs tentatives.")


# ---------------------------------------------------------------------------
# Interface publique
# ---------------------------------------------------------------------------

class GeminiService:
    """
    Service centralisé — SEUL endroit où l'API Gemini est appelée.

    Méthodes :
        stream_summary(text, style, processed)  → AsyncGenerator[str]
        stream_answer(document, question)        → AsyncGenerator[str]
        generate_title(summary)                  → str   (async)
        health_check()                           → dict  (async)
    """

    async def stream_summary(
        self,
        text: str,
        style: str = "concis",
        processed: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """Streame le résumé. Vérifie le cache avant d'appeler Gemini."""
        if not text or not text.strip():
            raise ValueError("Le texte ne peut pas être vide.")

        key = _cache_key(text, style)
        cached = _cache_get(key)
        if cached:
            yield f" (Cache)\n\n{cached}"
            return

        if processed is None:
            processed = {"key_content": text, "original_text": text}

        template = STYLE_PROMPTS.get(style, STYLE_PROMPTS["concis"])
        prompt = template.format(
            key_content=processed.get("key_content", text),
            text=processed.get("original_text", text),
        )

        logger.debug("stream_summary style=%s", style)

        full = ""
        async for token in _stream_gemini("summary", prompt):
            full += token
            yield token

        if full.strip():
            _cache_set(key, full)

    async def stream_answer(
        self,
        document: str,
        question: str,
    ) -> AsyncGenerator[str, None]:
        """Streame la réponse Q&A basée sur le document source."""
        if not question or not question.strip():
            raise ValueError("La question ne peut pas être vide.")

        excerpt = document[:10_000]
        if len(document) > 10_000:
            excerpt += "\n\n[... document tronqué ...]"

        prompt = f"Voici le document source :\n\n---\n{excerpt}\n---\n\nQuestion : {question}"

        async for token in _stream_gemini("qa", prompt):
            yield token

    async def generate_title(self, summary: str) -> str:
        """Génère un titre court (appel non-streamé, async)."""
        prompt = _TITLE_PROMPT_TEMPLATE.format(text=summary[:800])
        config = genai.types.GenerationConfig(max_output_tokens=30, temperature=0.5)

        # Retry avec rotation de clé si nécessaire
        for attempt in range(_key_rotator.total * 2):
            try:
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: _models.title.generate_content(prompt, generation_config=config),
                )
                if not response.candidates:
                    return "Résumé du document"
                title = response.candidates[0].content.parts[0].text.strip()
                title = title.strip('"\'«»').rstrip(".!?")
                logger.info("Titre : %s", title)
                return title or "Résumé du document"
            except google_exceptions.ResourceExhausted as exc:
                logger.warning("generate_title : quota épuisé, rotation…")
                if not _models.rotate_and_rebuild():
                    logger.error("generate_title : toutes les clés épuisées.")
                    return "Résumé du document"
            except Exception as exc:
                logger.error("generate_title : %s", exc)
                return "Résumé du document"
        return "Résumé du document"

    async def health_check(self) -> dict:
        for attempt in range(_key_rotator.total):
            try:
                loop = asyncio.get_running_loop()
                r = await loop.run_in_executor(
                    None,
                    lambda: _models.title.generate_content(
                        "Réponds uniquement 'ok'.",
                        generation_config=genai.types.GenerationConfig(max_output_tokens=5),
                    ),
                )
                if r.candidates:
                    return {
                        "status": "ok",
                        "model": _MODEL_NAME,
                        "active_key_index": _key_rotator._index + 1,
                        "total_keys": _key_rotator.total,
                    }
            except google_exceptions.ResourceExhausted:
                if not _models.rotate_and_rebuild():
                    break
            except Exception as exc:
                return {"status": "error", "detail": str(exc)}
        return {"status": "unknown"}

    @staticmethod
    def clear_cache() -> None:
        _cache.clear()
        logger.info("Cache Gemini vidé.")

    @staticmethod
    def cache_size() -> int:
        return len(_cache)


# Singleton exporté
gemini_service = GeminiService()