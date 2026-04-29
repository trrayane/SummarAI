from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Gemini — clé unique (rétrocompatibilité) ou liste de clés
    GEMINI_API_KEY: str = ""
    # Liste de clés séparées par des virgules dans .env :
    #   GEMINI_API_KEYS=key1,key2,key3,key4,key5
    GEMINI_API_KEYS: str = ""          # "key1,key2,key3"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.3
    GEMINI_MAX_TOKENS: int = 2048

    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "rayane"
    MYSQL_DATABASE: str = "ai_summarizer"

    # Serveur
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    ALLOWED_ORIGINS: List[str] = ["*"]

    def get_api_keys(self) -> List[str]:
        """
        Retourne la liste de toutes les clés disponibles.
        Priorité : GEMINI_API_KEYS (multi) > GEMINI_API_KEY (legacy).
        """
        if self.GEMINI_API_KEYS:
            keys = [k.strip() for k in self.GEMINI_API_KEYS.split(",") if k.strip()]
            if keys:
                return keys
        if self.GEMINI_API_KEY:
            return [self.GEMINI_API_KEY]
        return []

    class Config:
        env_file = ".env"


settings = Settings()