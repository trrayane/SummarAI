"""
services/gemini_service.py
Point d'entrée unique pour TOUS les appels à l'API Gemini.

Fixes vs version originale :
  - asyncio.get_event_loop() → asyncio.get_running_loop()
    (get_event_loop() est deprecated Python 3.10+ et lève DeprecationWarning
     dans un contexte async ; get_running_loop() est l'appel correct)
  - Cache cleanup optimisé : évite de modifier le dict pendant l'itération
"""

import asyncio
import hashlib
import logging
import threading
import time
from typing import AsyncGenerator, Optional

import google.generativeai as genai
import google.api_core.exceptions as google_exceptions

from config.settings import settings
from prompts.style_prompts import STYLE_PROMPTS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration SDK
# ---------------------------------------------------------------------------
genai.configure(api_key=settings.GEMINI_API_KEY)

_MODEL_NAME = settings.GEMINI_MODEL  # "gemini-2.5-flash"

_QA_SYSTEM_PROMPT = """
You are a precise document assistant. Your only job is to answer questions
based strictly on the document provided. Never add outside information.
Always reply in the same language as the question.
If the answer is not found in the document, say so clearly.
"""

_TITLE_PROMPT_TEMPLATE = (
    "Génère un titre court et accrocheur pour ce résumé :\n\n{text}\n\n"
    "Le titre doit être en anglais, ne pas dépasser 5 mots, et ne pas être une phrase complète."
    "Ne mets pas de point à la fin du titre."
    "Si tu ne peux pas générer un titre pertinent, réponds simplement 'Summary of the document'."
    "Le titre doit être en anglais, même si le résumé est dans une autre langue."
  
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
    # BUG FIX: copy keys before iterating to avoid RuntimeError on dict mutation
    now = time.time()
    expired = [k for k, v in _cache.items() if now > v["expires_at"]]
    for k in expired:
        _cache.pop(k, None)


# ---------------------------------------------------------------------------
# Modèles Gemini — singleton
# ---------------------------------------------------------------------------
class _Models:
    def __init__(self) -> None:
        self.summary = genai.GenerativeModel(
            model_name=_MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
        )
        self.qa = genai.GenerativeModel(
            model_name=_MODEL_NAME,
            system_instruction=_QA_SYSTEM_PROMPT,
        )
        self.title = genai.GenerativeModel(model_name=_MODEL_NAME)

    def default_config(self, **kwargs) -> genai.types.GenerationConfig:
        return genai.types.GenerationConfig(
            temperature=settings.GEMINI_TEMPERATURE,
            max_output_tokens=settings.GEMINI_MAX_TOKENS,
            **kwargs,
        )


_models = _Models()


# ---------------------------------------------------------------------------
# Helper de streaming async
# ---------------------------------------------------------------------------
def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, (
        google_exceptions.ServiceUnavailable,
        google_exceptions.DeadlineExceeded,
        google_exceptions.InternalServerError,
        google_exceptions.ResourceExhausted,
    ))


async def _stream_gemini(
    model: genai.GenerativeModel,
    prompt: str,
    gen_config: Optional[genai.types.GenerationConfig] = None,
    max_retries: int = 3,
) -> AsyncGenerator[str, None]:
    """
    Streame les tokens Gemini de façon 100% async.
    Le SDK synchrone tourne dans un thread ; les tokens transitent
    par une asyncio.Queue thread-safe. Retry avec backoff exponentiel.

    BUG FIX: asyncio.get_running_loop() remplace get_event_loop()
             qui est deprecated Python 3.10+ dans un contexte coroutine.
    """
    # FIX: get_running_loop() est l'API correcte dans une coroutine async
    loop = asyncio.get_running_loop()
    config = gen_config or _models.default_config()

    for attempt in range(1, max_retries + 1):
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
                        pass  # chunk bloqué par la sécurité Gemini
            except Exception as exc:
                errors.append(exc)
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, None)  # sentinelle

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
            if _is_retryable(exc) and attempt < max_retries:
                wait = 2 ** attempt
                logger.warning("Gemini retry %d/%d dans %ds : %s", attempt, max_retries, wait, exc)
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
            yield f"📦 (Cache)\n\n{cached}"
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
        async for token in _stream_gemini(_models.summary, prompt):
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

        async for token in _stream_gemini(_models.qa, prompt):
            yield token

    async def generate_title(self, summary: str) -> str:
        """Génère un titre court (appel non-streamé, async)."""
        prompt = _TITLE_PROMPT_TEMPLATE.format(text=summary[:800])
        config = genai.types.GenerationConfig(max_output_tokens=30, temperature=0.5)
        try:
            # FIX: get_running_loop() au lieu de get_event_loop()
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
        except Exception as exc:
            logger.error("generate_title : %s", exc)
            return "Résumé du document"

    async def health_check(self) -> dict:
        try:
            # FIX: get_running_loop() au lieu de get_event_loop()
            loop = asyncio.get_running_loop()
            r = await loop.run_in_executor(
                None,
                lambda: _models.title.generate_content(
                    "Réponds uniquement 'ok'.",
                    generation_config=genai.types.GenerationConfig(max_output_tokens=5),
                ),
            )
            if r.candidates:
                return {"status": "ok", "model": _MODEL_NAME}
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