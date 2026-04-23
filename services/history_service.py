"""
services/history_service.py
Stockage de l'historique des résumés avec cache par hash SHA-256.

Note : stockage en mémoire. Pour la persistance, brancher MySQL/Redis
en remplaçant _db et les méthodes save/get_recent/get_by_text_hash.
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Structure interne : liste de dicts + index par hash pour lookup O(1)
_db: list[dict] = []
_hash_index: dict[str, int] = {}  # hash → index dans _db


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class HistoryService:

    async def save(
        self,
        original_text: str,
        summary: str,
        style: str,
        word_count: int,
        title: str = "",
    ) -> None:
        """Sauvegarde un résumé. Met à jour l'entrée si le texte existe déjà."""
        h = _text_hash(original_text)

        entry = {
            "hash": h,
            "original_text": original_text,
            "summary": summary,
            "style": style,
            "title": title,
            "word_count": word_count,
            "created_at": datetime.now().isoformat(),
        }

        if h in _hash_index:
            # Mise à jour de l'entrée existante
            idx = _hash_index[h]
            _db[idx] = entry
            logger.debug("Historique mis à jour — hash %s…", h[:12])
        else:
            _db.append(entry)
            _hash_index[h] = len(_db) - 1
            logger.debug("Historique sauvegardé — hash %s…", h[:12])

    async def get_recent(self, limit: int = 10) -> list[dict]:
        """Retourne les `limit` résumés les plus récents (sans le texte source)."""
        recent = list(reversed(_db))[:limit]
        # On n'expose pas le texte source complet dans la liste
        return [
            {k: v for k, v in item.items() if k != "original_text"}
            for item in recent
        ]

    async def get_by_text_hash(self, text: str) -> Optional[dict]:
        """
        Recherche un résumé en cache par hash du texte source.
        Retourne {"summary": ..., "style": ...} ou None.
        """
        h = _text_hash(text)
        idx = _hash_index.get(h)
        if idx is None:
            return None
        entry = _db[idx]
        return {"summary": entry["summary"], "style": entry["style"]}

    async def clear(self) -> None:
        """Vide l'historique (utile pour les tests)."""
        _db.clear()
        _hash_index.clear()