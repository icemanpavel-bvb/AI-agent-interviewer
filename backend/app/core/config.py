"""Настройки приложения: переменные окружения и файл .env в корне репозитория."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # Значения по умолчанию — только для локальной разработки; в .env задаются настоящие.
    database_url: str = "postgresql+asyncpg://interviewer:interviewer@localhost:5432/interviewer"
    jwt_secret: str = "dev-only-change-me"
    invite_ttl_days: int = 7

    llm_provider: str = "ollama"
    llm_model: str = "gigachat-lightning"
    ollama_url: str = "http://localhost:11434"
    llm_temperature: float = 0.0
    llm_num_ctx: int = 4096
    # Ответ анализа — JSON с цитатой по каждому пункту (до 6): 400 токенов с запасом.
    llm_num_predict: int = 600
    llm_warmup_on_start: bool = True
    # Облачные модели и ключи к ним (D-013): путь от корня репозитория, файл в .gitignore.
    llm_keys_file: str = "llm_keys.json"
    gigachat_credentials: str = ""
    llm_mask_pii: bool = False

    max_base_questions: int = 10
    max_followups_per_question: int = 2
    postpone_days_default: int = 2

    scenarios_dir: str = "scenarios"
    demo_mode: bool = False
    public_base_url: str = "http://localhost:8080"

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")


settings = Settings()
