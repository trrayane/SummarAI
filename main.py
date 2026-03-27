"""
main.py
Point d'entrée de l'application AI Summarizer.
Lance le serveur FastAPI + initialise la base de données MySQL.
"""

import logging
import os
from contextlib import asynccontextmanager

import nltk
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import router
from services.history_service import init_db
from config.settings import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Téléchargement NLTK (silencieux si déjà présent)
# ---------------------------------------------------------------------------

def _download_nltk_data() -> None:
    packages = ["punkt", "stopwords", "punkt_tab"]
    for pkg in packages:
        try:
            nltk.download(pkg, quiet=True)
        except Exception as exc:
            logger.warning("NLTK '%s' non téléchargé : %s", pkg, exc)


# ---------------------------------------------------------------------------
# Lifespan : démarrage / arrêt
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Démarrage ──────────────────────────────────────────────────────────
    logger.info("🚀  Démarrage de AI Summarizer…")

    # 1. Données NLTK
    _download_nltk_data()
    logger.info("✅  NLTK prêt")

    # 2. Base de données MySQL
    try:
        await init_db()
        logger.info("✅  MySQL connecté — table 'summaries' prête")
    except Exception as exc:
        logger.warning("⚠️   MySQL non disponible (%s) — historique désactivé", exc)

    logger.info("✅  Serveur disponible sur http://localhost:%s", settings.PORT)
    logger.info("📖  Swagger UI       → http://localhost:%s/docs", settings.PORT)

    yield  # ── L'app tourne ici ────────────────────────────────────────────

    # ── Arrêt ──────────────────────────────────────────────────────────────
    logger.info("🛑  Arrêt du serveur.")


# ---------------------------------------------------------------------------
# Application FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Text Summarizer",
    description="Résumé automatique de textes et fichiers via Gemini + LangChain",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (dev : tout autoriser) ────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,   # ["*"] en dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes API ─────────────────────────────────────────────────────────────
app.include_router(router, prefix="/api/v1")

# ── Fichiers statiques (frontend) ──────────────────────────────────────────
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend() -> FileResponse:
        """Sert l'interface chatbot."""
        return FileResponse("static/index.html")
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "message": "AI Summarizer API",
            "docs": "/docs",
            "health": "/api/v1/health",
        }


# ---------------------------------------------------------------------------
# Lancement direct  →  python main.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,       # "0.0.0.0"
        port=settings.PORT,       # 8000
        reload=settings.DEBUG,    # True en dev
        log_level="info",
    )