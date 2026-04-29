"""
memory/session_store.py
Stockage en mémoire du texte source par session pour le mode Q&A.
Chaque résumé génère un session_id unique permettant de poser
des questions sur le document original.
"""

import time

# Durée de vie d'une session en secondes (2h)
SESSION_TTL = 7200

# Structure : {session_id: {"text": str, "expires_at": float}}
_store: dict[str, dict] = {}


def save_document(session_id: str, text: str) -> None:
    """Sauvegarde le texte source associé à un session_id."""
    _store[session_id] = {
        "text": text,
        "expires_at": time.time() + SESSION_TTL,
    }
    _cleanup()


def get_document(session_id: str) -> str | None:
    """
    Retourne le texte source pour ce session_id, ou None si expiré/inexistant.
    """
    entry = _store.get(session_id)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        del _store[session_id]
        return None
    return entry["text"]


def _cleanup() -> None:
    """Supprime les sessions expirées (appelé à chaque écriture)."""
    now = time.time()
    expired = [sid for sid, v in _store.items() if now > v["expires_at"]]
    for sid in expired:
        del _store[sid]