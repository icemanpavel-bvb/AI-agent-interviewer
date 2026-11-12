"""Общие зависимости эндпоинтов: модель, хранилище сессий, демо-режим."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.config import settings
from app.interview.store import SessionStore, store
from app.llm.base import LLMProvider


def get_provider(request: Request) -> LLMProvider:
    return request.app.state.provider


def get_store() -> SessionStore:
    return store


def require_demo() -> None:
    if not settings.demo_mode:
        raise HTTPException(404, "Демо-режим выключен (DEMO_MODE=false)")


ProviderDep = Annotated[LLMProvider, Depends(get_provider)]
StoreDep = Annotated[SessionStore, Depends(get_store)]
