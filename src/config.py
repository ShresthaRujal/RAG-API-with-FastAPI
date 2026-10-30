
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):

    APP_NAME: str = "Personal AI Directory"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    CHROMA_PATH: str = "./chroma_db"
    COLLECTION_NAME: str = "personal_profiles"

    OLLAMA_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    LLM_MODEL: str = "qwen2.5:0.5b"

    TOP_K: int = 3

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def chroma_path(self):
        path = Path(self.CHROMA_PATH)
        return path if path.is_absolute() else BASE_DIR / path


settings = Settings()
