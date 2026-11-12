"""Точка входа FastAPI: подключение роутеров, CORS, запуск Scheduler при старте."""

from fastapi import FastAPI

from app.api.v1 import router as api_v1
from app.jobs.scheduler import start_scheduler, stop_scheduler

app = FastAPI(title="AI Interviewer", version="0.1.0")
app.include_router(api_v1, prefix="/api/v1")


@app.on_event("startup")
async def _startup() -> None:
    start_scheduler()


@app.on_event("shutdown")
async def _shutdown() -> None:
    stop_scheduler()
