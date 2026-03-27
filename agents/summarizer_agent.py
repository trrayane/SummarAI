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


class SummarizerAgent:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT,
        )
        self.processor = NLTKProcessor()
        self.file_parser = FileParser()
        self.history = HistoryService()
        self.memory = []  # ✅ plus besoin de LangChain

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

        token_queue = queue.Queue()
        error_holder = []

        def run_gemini():
            try:
                response = self.model.generate_content(user_prompt, stream=True)
                for chunk in response:
                    try:
                        t = chunk.text
                        if t:
                            token_queue.put(t)
                    except Exception:
                        pass
            except Exception as e:
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

        # ✅ remplace save_context
        self.memory.append({
            "input": f"Résume en style {style}",
            "output": summary
        })