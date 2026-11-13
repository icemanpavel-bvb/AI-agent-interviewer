"""Общие зависимости эндпоинтов: реестр моделей, хранилище сессий, демо-режим."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.config import settings
from app.interview.store import SessionStore, store
from app.llm.registry import ModelRegistry


def get_registry(request: Request) -> ModelRegistry:
    return request.app.state.registry


def get_store() -> SessionStore:
    return store


def require_demo() -> None:
    if not settings.demo_mode:
        raise HTTPException(404, "Демо-режим выключен (DEMO_MODE=false)")


RegistryDep = Annotated[ModelRegistry, Depends(get_registry)]
StoreDep = Annotated[SessionStore, Depends(get_store)]
