import asyncio
import queue
import threading

import google.generativeai as genai
from preprocessing.nltk_processor import NLTKProcessor
from prompts.style_prompts import STYLE_PROMPTS, SYSTEM_PROMPT
from tools.file_parser import FileParser
from services.history_service import HistoryService
from config.settings import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

QA_SYSTEM_PROMPT = """
You are a precise document assistant. Your only job is to answer questions
based strictly on the document provided. Never add outside information.
Always reply in the same language as the question.
If the answer is not found in the document, say so clearly.
"""


class SummarizerAgent:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT,
        )
        self.qa_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=QA_SYSTEM_PROMPT,
        )
        self.processor = NLTKProcessor()
        self.file_parser = FileParser()
        self.history = HistoryService()
        self.memory = []

    # ------------------------------------------------------------------
    # Résumé (existant, inchangé)
    # ------------------------------------------------------------------

    async def summarize(self, text: str, style: str = "concis", file=None):
        if file and file.filename:
            text = self.file_parser.parse(file)

        if not text or not text.strip():
            yield "⚠️ Aucun texte fourni."
            return

        processed = self.processor.preprocess(text)

        cached = await self.history.get_by_text_hash(text)
        if cached and cached.get("style") == style:
            yield f"📦 (Cache)\n\n{cached['summary']}"
            return

        style_template = STYLE_PROMPTS.get(style, STYLE_PROMPTS["concis"])
        user_prompt = style_template.format(
            key_content=processed["key_content"],
            text=processed["original_text"]
        )

        print(f"[DEBUG] style: {style}")
        print(f"[DEBUG] prompt envoyé:\n{user_prompt[:300]}")

        token_queue = queue.Queue()
        error_holder = []

        def run_gemini():
            try:
                response = self.model.generate_content(user_prompt, stream=True)
                for chunk in response:
                    try:
                        t = chunk.text
                        print(f"[DEBUG] chunk reçu: '{t}'")
                        if t:
                            token_queue.put(t)
                    except Exception as e:
                        print(f"[DEBUG] erreur chunk: {e}")
            except Exception as e:
                print(f"[DEBUG] erreur gemini: {e}")
                error_holder.append(str(e))
            finally:
                token_queue.put(None)

        t = threading.Thread(target=run_gemini, daemon=True)
        t.start()

        summary = ""
        while True:
            try:
                token = token_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.005)
                continue

            if token is None:
                break
            summary += token
            yield token

        t.join(timeout=5)

        if error_holder:
            yield f"\n\n⚠️ Erreur : {error_holder[0]}"
            return

        await self.history.save(
            original_text=text,
            summary=summary,
            style=style,
            word_count=processed["word_count"]
        )

        self.memory.append({
            "input": f"Résume en style {style}",
            "output": summary
        })

    # ------------------------------------------------------------------
    # Q&A — répondre à une question sur le document source
    # ------------------------------------------------------------------

    async def answer_question(self, document: str, question: str):
        """
        Génère une réponse en streaming à une question sur le document fourni.

        Args:
            document: Texte source original (extrait lors du résumé).
            question: Question de l'utilisateur.

        Yields:
            Tokens de la réponse.
        """
        # Limiter le document à ~10 000 chars pour ne pas dépasser la fenêtre
        doc_excerpt = document[:10_000]
        if len(document) > 10_000:
            doc_excerpt += "\n\n[... document tronqué pour la longueur ...]"

        prompt = (
            f"Voici le document source :\n\n"
            f"---\n{doc_excerpt}\n---\n\n"
            f"Question : {question}"
        )

        token_queue = queue.Queue()
        error_holder = []

        def run_gemini():
            try:
                response = self.qa_model.generate_content(prompt, stream=True)
                for chunk in response:
                    try:
                        t = chunk.text
                        if t:
                            token_queue.put(t)
                    except Exception as e:
                        print(f"[DEBUG QA] erreur chunk: {e}")
            except Exception as e:
                print(f"[DEBUG QA] erreur gemini: {e}")
                error_holder.append(str(e))
            finally:
                token_queue.put(None)

        t = threading.Thread(target=run_gemini, daemon=True)
        t.start()

        while True:
            try:
                token = token_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.005)
                continue

            if token is None:
                break
            yield token

        t.join(timeout=5)

        if error_holder:
            yield f"\n\n⚠️ Erreur : {error_holder[0]}"