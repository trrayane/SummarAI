from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Gemini
    GEMINI_API_KEY: str = ""
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

    class Config:
        env_file = ".env"


settings = Settings()