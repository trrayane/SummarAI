"""
services/gemini_service.py
Service Gemini — Gestion des appels à l'API Gemini via LangChain
avec cache, streaming et gestion d'erreurs.
"""

import hashlib
import logging
from typing import AsyncGenerator, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache mémoire simple  (remplacé par MySQL si disponible — voir history_service)
# ---------------------------------------------------------------------------
_memory_cache: dict[str, str] = {}


def _cache_key(text: str, style: str) -> str:
    """Génère une clé de cache déterministe à partir du texte + style."""
    payload = f"{style}::{text}"
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Initialisation du modèle
# ---------------------------------------------------------------------------

def _build_llm(streaming: bool = False) -> ChatGoogleGenerativeAI:
    """
    Instancie le modèle Gemini 1.5 Flash.

    Args:
        streaming: Active le mode streaming token-par-token.

    Returns:
        Instance ChatGoogleGenerativeAI configurée.
    """
    callbacks = [StreamingStdOutCallbackHandler()] if streaming else []

    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,               # "gemini-1.5-flash"
        google_api_key=settings.GEMINI_API_KEY,
        temperature=settings.GEMINI_TEMPERATURE,   # 0.3 par défaut
        max_output_tokens=settings.GEMINI_MAX_TOKENS,
        streaming=streaming,
        callbacks=callbacks,
    )


# ---------------------------------------------------------------------------
# Service principal
# ---------------------------------------------------------------------------

class GeminiService:
    """
    Encapsule toutes les interactions avec l'API Gemini.

    Utilisation :
        service = GeminiService()
        result  = await service.summarize(text, style="concis")
    """

    def __init__(self) -> None:
        self._llm = _build_llm(streaming=False)
        self._llm_stream = _build_llm(streaming=True)

    # ------------------------------------------------------------------
    # Résumé standard (réponse complète)
    # ------------------------------------------------------------------

    async def summarize(
        self,
        text: str,
        style: str = "concis",
        system_prompt: Optional[str] = None,
        use_cache: bool = True,
    ) -> str:
        """
        Génère un résumé complet du texte fourni.

        Args:
            text:          Texte source à résumer.
            style:         Style souhaité ("concis" | "détaillé" | "bullet_points").
            system_prompt: Prompt système personnalisé (optionnel).
            use_cache:     Vérifie le cache mémoire avant d'appeler l'API.

        Returns:
            Résumé sous forme de chaîne de caractères.

        Raises:
            ValueError: Si le texte est vide.
            RuntimeError: En cas d'échec de l'appel API.
        """
        if not text or not text.strip():
            raise ValueError("Le texte à résumer ne peut pas être vide.")

        # Vérification du cache
        key = _cache_key(text, style)
        if use_cache and key in _memory_cache:
            logger.info("Cache hit pour la clé %s", key[:12])
            return _memory_cache[key]

        messages = self._build_messages(text, style, system_prompt)

        try:
            response = await self._llm.ainvoke(messages)
            result: str = response.content.strip()
        except Exception as exc:
            logger.error("Erreur Gemini API : %s", exc)
            raise RuntimeError(f"Échec de l'appel Gemini : {exc}") from exc

        # Mise en cache
        if use_cache:
            _memory_cache[key] = result

        return result

    # ------------------------------------------------------------------
    # Résumé en streaming (token par token)
    # ------------------------------------------------------------------

    async def summarize_stream(
        self,
        text: str,
        style: str = "concis",
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Génère un résumé en streaming (Server-Sent Events).

        Yields:
            Fragments de texte (tokens) au fur et à mesure.

        Example (FastAPI endpoint) :
            return StreamingResponse(
                service.summarize_stream(text, style),
                media_type="text/event-stream",
            )
        """
        if not text or not text.strip():
            raise ValueError("Le texte à résumer ne peut pas être vide.")

        messages = self._build_messages(text, style, system_prompt)

        try:
            async for chunk in self._llm_stream.astream(messages):
                token: str = chunk.content
                if token:
                    yield token
        except Exception as exc:
            logger.error("Erreur Gemini streaming : %s", exc)
            raise RuntimeError(f"Échec du streaming Gemini : {exc}") from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(
        text: str,
        style: str,
        system_prompt: Optional[str],
    ) -> list:
        """
        Construit la liste de messages LangChain à envoyer au modèle.

        Args:
            text:          Texte source.
            style:         Style de résumé.
            system_prompt: Prompt système personnalisé (prioritaire sur le style).

        Returns:
            Liste [SystemMessage, HumanMessage].
        """
        # Import local pour éviter la circularité
        from prompts.style_prompts import get_system_prompt

        sys_content = system_prompt or get_system_prompt(style)

        return [
            SystemMessage(content=sys_content),
            HumanMessage(content=f"Voici le texte à résumer :\n\n{text}"),
        ]

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    @staticmethod
    def clear_cache() -> None:
        """Vide le cache mémoire (utile pour les tests)."""
        _memory_cache.clear()
        logger.info("Cache mémoire Gemini vidé.")

    @staticmethod
    def cache_size() -> int:
        """Retourne le nombre d'entrées en cache."""
        return len(_memory_cache)

    async def health_check(self) -> dict:
        """
        Vérifie la connectivité avec l'API Gemini.

        Returns:
            {"status": "ok"} ou {"status": "error", "detail": "..."}
        """
        try:
            probe = await self._llm.ainvoke(
                [HumanMessage(content="Réponds uniquement 'ok'.")]
            )
            if probe.content:
                return {"status": "ok", "model": settings.GEMINI_MODEL}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}
        return {"status": "unknown"}


# ---------------------------------------------------------------------------
# Singleton exporté
# ---------------------------------------------------------------------------

gemini_service = GeminiService()