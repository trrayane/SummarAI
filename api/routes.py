import io
import uuid

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

from agents.summarizer_agent import SummarizerAgent
from services.history_service import HistoryService
from memory.session_store import save_document, get_document
from tools.web_scraper import extract_text_from_url

router = APIRouter()
agent = SummarizerAgent()


class FileWrapper:
    """Wrapper pour passer les bytes du fichier à file_parser comme si c'était un UploadFile."""
    def __init__(self, filename: str, contents: bytes):
        self.filename = filename
        self.file = io.BytesIO(contents)


# ---------------------------------------------------------------------------
# POST /summarize
# ---------------------------------------------------------------------------

@router.post("/summarize")
async def summarize(
    text: str = Form(default=""),
    url: str = Form(default=""),
    style: str = Form(default="concis"),
    file: UploadFile = File(default=None)
):
    """
    Résume un texte brut, un fichier uploadé ou une page web via URL.
    Retourne un stream SSE + un session_id pour le mode Q&A.
    """
    # 1. Résolution de la source : URL > fichier > texte brut
    file_wrapper = None
    source_text = text

    if url and url.strip():
        try:
            source_text = await extract_text_from_url(url.strip())
        except (ValueError, RuntimeError) as exc:
            async def error_stream():
                yield f"data: ⚠️ Impossible de charger l'URL : {exc}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")

    elif file and file.filename:
        contents = await file.read()
        file_wrapper = FileWrapper(filename=file.filename, contents=contents)
        # Le texte sera extrait par summarizer_agent via file_parser
        source_text = ""

    # 2. Générer un session_id et sauvegarder la source pour le Q&A
    session_id = str(uuid.uuid4())

    async def stream_response():
        full_text_for_session = source_text  # sera complété si fichier

        # Envoyer le session_id en premier chunk spécial
        yield f"data: __SESSION__{session_id}__\n\n"

        collected = []
        async for token in agent.summarize(text=source_text, style=style, file=file_wrapper):
            collected.append(token)
            yield f"data: {token}\n\n"

        yield "data: [DONE]\n\n"

        # Sauvegarder le texte source extrait (utile si c'était un fichier)
        # On utilise source_text ; pour les fichiers, le parser a déjà travaillé
        # côté agent — on stocke ce qu'on a
        save_document(session_id, full_text_for_session or " ".join(collected))

    return StreamingResponse(stream_response(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# POST /ask  — mode Q&A sur le document résumé
# ---------------------------------------------------------------------------

@router.post("/ask")
async def ask_question(
    session_id: str = Form(...),
    question: str = Form(...)
):
    """
    Répond à une question sur le document original associé au session_id.
    Retourne un stream SSE.
    """
    document = get_document(session_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail="Session introuvable ou expirée. Veuillez régénérer un résumé."
        )

    if not question or not question.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide.")

    async def qa_stream():
        async for token in agent.answer_question(document=document, question=question.strip()):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(qa_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# GET /history
# ---------------------------------------------------------------------------

@router.get("/history")
async def get_history(limit: int = 10):
    service = HistoryService()
    return await service.get_recent(limit)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok"}