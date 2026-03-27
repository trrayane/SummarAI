import io
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from agents.summarizer_agent import SummarizerAgent
from services.history_service import HistoryService

router = APIRouter()
agent = SummarizerAgent()


class FileWrapper:
    """Wrapper pour passer les bytes du fichier à file_parser comme si c'était un UploadFile."""
    def __init__(self, filename: str, contents: bytes):
        self.filename = filename
        self.file = io.BytesIO(contents)


@router.post("/summarize")
async def summarize(
    text: str = Form(default=""),
    style: str = Form(default="concis"),
    file: UploadFile = File(default=None)
):
    # ✅ Lire les bytes AVANT que FastAPI ferme le fichier
    file_wrapper = None
    if file and file.filename:
        contents = await file.read()
        file_wrapper = FileWrapper(filename=file.filename, contents=contents)

    async def stream_response():
        async for token in agent.summarize(text=text, style=style, file=file_wrapper):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")


@router.get("/history")
async def get_history(limit: int = 10):
    service = HistoryService()
    return await service.get_recent(limit)


@router.get("/health")
async def health():
    return {"status": "ok"}