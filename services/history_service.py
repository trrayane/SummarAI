from datetime import datetime

# simple in-memory storage
memory_db = []


async def init_db():
    """Fonction vide — stockage en memoire, pas de DB a initialiser."""
    pass


class HistoryService:

    async def save(self, original_text: str, summary: str, style: str, word_count: int):
        memory_db.append({
            "original_text": original_text,
            "summary": summary,
            "style": style,
            "word_count": word_count,
            "created_at": datetime.now().isoformat()
        })

    async def get_recent(self, limit: int = 10):
        return memory_db[::-1][:limit]

    async def get_by_text_hash(self, text: str):
        for item in memory_db:
            if item["original_text"] == text:
                return {
                    "summary": item["summary"],
                    "style": item["style"]
                }
        return None