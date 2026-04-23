"""
agents/summarizer_agent.py
Orchestrateur du pipeline de résumé et Q&A.

Responsabilités :
    - Parsing des fichiers (FileParser)
    - Vérification de la langue (LanguageDetector) — anglais uniquement
    - Prétraitement NLP en thread (NLTKProcessor)
    - Délégation à GeminiService pour tous les appels API
    - Sauvegarde de l'historique (HistoryService)
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional

from services.gemini_service import gemini_service
from preprocessing.nltk_processor import NLTKProcessor
from tools.file_parser import FileParser
from tools.language_detector import is_english, get_rejection_message
from services.history_service import HistoryService

logger = logging.getLogger(__name__)

# Token spécial émis quand la langue n'est pas l'anglais.
# Routes.py l'intercepte pour NE PAS activer le Q&A et NE PAS sauvegarder la session.
LANG_REJECTED_TOKEN = "__LANG_REJECTED__"


class SummarizerAgent:
    def __init__(self):
        self.processor = NLTKProcessor()
        self.file_parser = FileParser()
        self.history = HistoryService()

    # ------------------------------------------------------------------
    # Résumé principal (streamé)
    # ------------------------------------------------------------------

    async def summarize(
        self,
        text: str,
        style: str = "concis",
        file=None,
    ) -> AsyncGenerator[str, None]:
        """
        Pipeline complet : parse → détection langue → NLP → stream Gemini → titre → cache.

        Yields:
            - LANG_REJECTED_TOKEN suivi du message d'erreur si la langue n'est pas l'anglais.
            - Tokens du résumé + "__TITLE__<titre>__" si la langue est l'anglais.
        """
        # 1. Parsing fichier si fourni
        if file and file.filename:
            loop = asyncio.get_event_loop()
            try:
                text = await loop.run_in_executor(None, self.file_parser.parse, file)
            except ValueError as exc:
                yield f"⚠️ Parsing error: {exc}"
                return

        if not text or not text.strip():
            yield "⚠️ No text provided."
            return

        # ----------------------------------------------------------------
        # 2. VÉRIFICATION DE LA LANGUE — anglais uniquement
        # ----------------------------------------------------------------
        if not is_english(text):
            logger.info("Texte rejeté — langue non-anglaise détectée.")
            # On émet le token de rejet EN PREMIER pour que routes.py
            # sache qu'il ne faut PAS stocker la session ni activer le Q&A.
            yield LANG_REJECTED_TOKEN
            yield get_rejection_message(text)
            return

        # 3. Prétraitement NLP (non-bloquant)
        loop = asyncio.get_event_loop()
        processed = await loop.run_in_executor(None, self.processor.preprocess, text)

        # 4. Vérification cache historique (style identique)
        cached = await self.history.get_by_text_hash(text)
        if cached and cached.get("style") == style:
            logger.debug("Cache historique hit")
            yield f"📦 (Cache)\n\n{cached['summary']}"
            return

        # 5. Streaming via GeminiService
        full_summary = ""
        try:
            async for token in gemini_service.stream_summary(
                text=text,
                style=style,
                processed=processed,
            ):
                full_summary += token
                yield token
        except RuntimeError as exc:
            yield f"\n\n⚠️ Error: {exc}"
            return

        if not full_summary.strip():
            yield "\n\n⚠️ No response received from Gemini."
            return

        # 6. Génération du titre
        title = await gemini_service.generate_title(full_summary)
        yield f"__TITLE__{title}__"

        # 7. Sauvegarde historique
        await self.history.save(
            original_text=text,
            summary=full_summary,
            style=style,
            word_count=processed.get("word_count", 0),
            title=title,
        )

        logger.info(
            "Résumé généré — style=%s, mots=%d",
            style, processed.get("word_count", 0)
        )

    # ------------------------------------------------------------------
    # Q&A (streamé)
    # ------------------------------------------------------------------

    async def answer_question(
        self,
        document: str,
        question: str,
    ) -> AsyncGenerator[str, None]:
        """
        Streame une réponse à une question sur le document source.
        Appelé uniquement si la session est valide (langue anglaise confirmée).
        """
        try:
            async for token in gemini_service.stream_answer(
                document=document,
                question=question,
            ):
                yield token
        except (RuntimeError, ValueError) as exc:
            yield f"\n\n⚠️ Error: {exc}"