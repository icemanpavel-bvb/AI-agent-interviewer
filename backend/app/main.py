"""Точка входа FastAPI.

Запуск для разработки (из папки backend):
    DEMO_MODE=true uvicorn app.main:app --reload

При DEMO_MODE модель прогревается в фоне при старте, чтобы первый ответ в чате не ждал ~30 с.
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import router as api_v1
from app.core.config import ROOT, settings
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.llm.base import LLMError
from app.llm.ollama import OllamaProvider
from app.llm.registry import ModelRegistry

log = logging.getLogger("app")


def make_provider() -> OllamaProvider:
    return OllamaProvider(
        settings.llm_model,
        settings.ollama_url,
        temperature=settings.llm_temperature,
        num_ctx=settings.llm_num_ctx,
        num_predict=settings.llm_num_predict,
    )


def _warmup(provider: OllamaProvider) -> None:
    try:
        provider.warmup()
        log.info("модель %s прогрета", provider.model)
    except LLMError as e:
        log.warning("прогрев модели не удался: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    local = make_provider()
    app.state.registry = ModelRegistry(
        local, ROOT / settings.llm_keys_file, max_tokens=settings.llm_num_predict
    )
    if settings.llm_warmup_on_start and settings.demo_mode:
        threading.Thread(target=_warmup, args=(local,), daemon=True).start()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="AI Interviewer", version="0.2.0", lifespan=lifespan)
app.include_router(api_v1, prefix="/api/v1")
