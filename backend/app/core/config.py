"""Настройки приложения из переменных окружения (.env)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    invite_ttl_days: int = 7

    llm_provider: str = "ollama"
    llm_model: str = "gigachat-lightning"
    ollama_url: str = "http://localhost:11434"
    llm_temperature: float = 0.0
    llm_num_ctx: int = 4096
    llm_num_predict: int = 200
    llm_warmup_on_start: bool = True
    gigachat_credentials: str = ""
    llm_mask_pii: bool = False

    max_base_questions: int = 10
    max_followups_per_question: int = 2
    postpone_days_default: int = 2

    scenarios_dir: str = "scenarios"
    demo_mode: bool = False
    public_base_url: str = "http://localhost:8080"

    class Config:
        env_file = ".env"


settings = Settings()  # type: ignore[call-arg]
