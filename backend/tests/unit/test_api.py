"""API демо и чата на фейковой модели: старт, ход, недоступность модели, протокол."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from app.api.deps import get_registry, get_store
from app.core.config import settings
from app.interview.store import SessionStore
from app.llm.base import LLMUnavailable
from app.llm.fake import FakeLLM
from app.llm.registry import ModelRegistry
from app.main import app


def cover_all(messages):
    """Фейковый анализ: все пункты раскрыты, цитата — первые слова ответа."""
    user = messages[1]["content"]
    answer = user.split("<answer>")[1].split("</answer>")[0].strip().split("\n")[-1]
    ids = [line[2:].split(":")[0] for line in user.splitlines() if line.startswith("- p")]
    quote = " ".join(answer.split()[:3])
    return {
        "intent": "answer",
        "probes": [{"id": i, "status": "covered", "quote": quote} for i in ids],
    }


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "llm_warmup_on_start", False)
    llm = FakeLLM(default=cover_all)
    registry = ModelRegistry(llm, tmp_path / "llm_keys.json")
    app.dependency_overrides[get_registry] = lambda: registry
    sessions = SessionStore()
    app.dependency_overrides[get_store] = lambda: sessions
    with TestClient(app) as c:
        c.llm = llm
        c.registry = registry
        yield c
    app.dependency_overrides.clear()


def test_scenarios_list(client):
    cards = {c["id"]: c for c in client.get("/api/v1/demo/scenarios").json()}
    assert {"ml_junior", "omto_analyst", "ml_middle", "student_course"} <= set(cards)
    assert cards["student_course"]["session_size"] == 10
    assert cards["student_course"]["topics"] and not cards["ml_junior"]["topics"]


def test_full_flow(client):
    r = client.post(
        "/api/v1/demo/start", json={"scenario_id": "student_course", "size": 2, "seed": 1}
    )
    assert r.status_code == 201
    s = r.json()
    token = s["token"]
    assert s["total_questions"] == 2 and s["question_number"] == 1
    assert [m["kind"] for m in s["messages"]] == ["greeting", "base_question"]

    s = client.post(
        f"/api/v1/interview/{token}/messages", json={"text": "Подробный ответ по теме"}
    ).json()
    assert s["question_number"] == 2
    assert s["debug"]["completeness"] == "complete" and s["debug"]["question_number"] == 1

    s = client.post(
        f"/api/v1/interview/{token}/messages", json={"text": "Второй подробный ответ"}
    ).json()
    assert s["finished"] and s["messages"][-1]["kind"] == "closing"

    p = client.get(f"/api/v1/interview/{token}/protocol").json()
    assert p["criteria"] and "references" in p
    assert (
        client.post(f"/api/v1/interview/{token}/messages", json={"text": "ещё"}).status_code == 409
    )


def test_model_unavailable_keeps_state(client):
    token = client.post("/api/v1/demo/start", json={"scenario_id": "ml_junior"}).json()["token"]

    def down(_):
        raise LLMUnavailable("Ollama недоступна")

    client.llm.responses.append(down)
    r = client.post(f"/api/v1/interview/{token}/messages", json={"text": "ответ"})
    assert r.status_code == 503
    s = client.get(f"/api/v1/interview/{token}").json()
    assert len(s["messages"]) == 2 and s["question_number"] == 1  # ответ не засчитан


def test_job_interview_has_no_references_and_stop(client):
    token = client.post("/api/v1/demo/start", json={"scenario_id": "ml_junior"}).json()["token"]
    s = client.post(f"/api/v1/interview/{token}/stop").json()
    assert s["finished"] and s["stopped"]
    assert "references" not in client.get(f"/api/v1/interview/{token}/protocol").json()


def test_errors(client, monkeypatch):
    assert client.post("/api/v1/demo/start", json={"scenario_id": "nope"}).status_code == 404
    bad_topic = {"scenario_id": "ml_junior", "topic": "J01"}
    assert client.post("/api/v1/demo/start", json=bad_topic).status_code == 400
    assert client.get("/api/v1/interview/unknown").status_code == 404
    monkeypatch.setattr(settings, "demo_mode", False)
    assert client.get("/api/v1/demo/scenarios").status_code == 404


def test_session_survives_restart(tmp_path):
    """Сессия сохраняется на диск и поднимается новым хранилищем (как после перезапуска сервера)."""
    from app.interview.runner import InterviewRunner
    from app.scenarios import load_scenario

    first = SessionStore(persist_dir=tmp_path)
    runner = InterviewRunner(load_scenario("ml_junior"), FakeLLM())
    runner.start()
    entry = first.create(runner)

    second = SessionStore(persist_dir=tmp_path)  # «новый процесс»
    restored = second.get(entry.token)
    assert restored is not None and restored.runner.provider is None
    assert [t.kind for t in restored.runner.transcript] == ["greeting", "base_question"]
    assert second.get("../../etc/passwd") is None  # токен проверяется перед обращением к диску


def test_too_long_message_rejected(client):
    token = client.post("/api/v1/demo/start", json={"scenario_id": "ml_junior"}).json()["token"]
    assert (
        client.post(f"/api/v1/interview/{token}/messages", json={"text": "а" * 3001}).status_code
        == 422
    )


def test_models_and_cloud_choice(client):
    models = client.get("/api/v1/demo/models").json()
    assert [m["id"] for m in models] == ["local"]
    r = client.post("/api/v1/demo/start", json={"scenario_id": "ml_junior", "model": "groq/нет"})
    assert r.status_code == 400

    cloud = FakeLLM(default=cover_all)
    client.registry.keys_file.write_text(
        '{"groq/llama-3.3-70b-versatile": "gsk_secret", "_comment": "x"}', encoding="utf-8"
    )
    models = client.get("/api/v1/demo/models").json()
    assert [m["id"] for m in models] == ["local", "groq/llama-3.3-70b-versatile"]
    assert "gsk_secret" not in str(models)
    client.registry.get("groq/llama-3.3-70b-versatile")  # создаём провайдер и подменяем фейком
    client.registry._providers["groq/llama-3.3-70b-versatile"] = cloud

    s = client.post(
        "/api/v1/demo/start",
        json={"scenario_id": "ml_junior", "model": "groq/llama-3.3-70b-versatile"},
    ).json()
    assert s["model"] == "groq/llama-3.3-70b-versatile" and not s["model_local"]
    client.post(f"/api/v1/interview/{s['token']}/messages", json={"text": "Пять лет делал модели."})
    assert cloud.requests and not client.llm.requests  # ответ проверила выбранная модель
    proto = client.get(f"/api/v1/interview/{s['token']}/protocol").json()
    assert proto["llm"]["model"] == "groq/llama-3.3-70b-versatile"

    # ключ убрали из файла — ход не засчитывается, понятная ошибка
    client.registry.keys_file.write_text("{}", encoding="utf-8")
    import os
    import time

    os.utime(client.registry.keys_file, (time.time() + 5, time.time() + 5))
    r = client.post(f"/api/v1/interview/{s['token']}/messages", json={"text": "ещё"})
    assert r.status_code == 503 and "llm_keys.json" in r.json()["detail"]
