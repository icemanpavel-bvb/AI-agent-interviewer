"""Облачные модели (D-013): разбор llm_keys.json и OpenAI-совместимый клиент на локальном фейковом сервере."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.llm import openai_compat
from app.llm.base import LLMUnavailable
from app.llm.fake import FakeLLM
from app.llm.openai_compat import OpenAICompatProvider
from app.llm.registry import ModelRegistry, parse_keys


def test_parse_keys_short_and_full(tmp_path):
    f = tmp_path / "llm_keys.json"
    f.write_text(
        json.dumps(
            {
                "_comment": "пример",
                "groq/llama-3.3-70b-versatile": "gsk_1",
                "openrouter/openai/gpt-oss-120b:free": "sk-or-1",
                "моя": {
                    "base_url": "http://x/v1",
                    "model": "m",
                    "api_key": "k",
                    "json_mode": False,
                },
                "незаполненная/модель": "<ваш ключ>",
                "неизвестный/сервис": "k",
            }
        ),
        encoding="utf-8",
    )
    specs = parse_keys(f)
    assert set(specs) == {
        "groq/llama-3.3-70b-versatile",
        "openrouter/openai/gpt-oss-120b:free",
        "моя",
    }
    assert specs["openrouter/openai/gpt-oss-120b:free"]["model"] == "openai/gpt-oss-120b:free"
    assert specs["groq/llama-3.3-70b-versatile"]["base_url"].startswith("https://api.groq.com")

    reg = ModelRegistry(FakeLLM(), f)
    assert reg.list()[0].id == "local"
    assert "gsk_1" not in repr(reg.list()) and "gsk_1" not in repr(
        reg.get("groq/llama-3.3-70b-versatile")
    )
    with pytest.raises(LLMUnavailable):
        reg.get("нет-такой")
    assert ModelRegistry(FakeLLM(), tmp_path / "нет.json").list()[0].id == "local"


class FakeAPI(BaseHTTPRequestHandler):
    """Ведёт себя как OpenAI-совместимый сервис; поведение задаёт атрибут server.mode."""

    def log_message(self, *args):
        pass

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, {"data": []})

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        srv = self.server
        srv.seen.append((self.path, dict(self.headers), body))
        if self.path.endswith("/oauth"):
            return self._send(200, {"access_token": "tok-1", "expires_at": 9_999_999_999_000})
        req = json.loads(body)
        if srv.mode == "no_json_mode" and "response_format" in req:
            return self._send(400, {"error": {"message": "response_format is not supported"}})
        if srv.mode == "rate_limit":
            return self._send(429, {"error": {"message": "limit for key gsk_secret"}})
        self._send(
            200,
            {
                "choices": [{"message": {"content": '{"value": 1}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            },
        )


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), FakeAPI)
    srv.mode, srv.seen = "ok", []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    srv.base = f"http://127.0.0.1:{srv.server_port}/v1"
    yield srv
    srv.shutdown()


def test_chat_json_mode_and_fallback(server):
    p = OpenAICompatProvider("m", server.base, "gsk_secret", provider="groq")
    r = p.chat([{"role": "user", "content": "x"}], json_schema={})
    assert r.text == '{"value": 1}' and r.prompt_tokens == 10
    _, headers, body = server.seen[-1]
    assert headers["Authorization"] == "Bearer gsk_secret"
    assert json.loads(body)["response_format"] == {"type": "json_object"}

    server.mode = "no_json_mode"
    assert p.chat([{"role": "user", "content": "x"}], json_schema={}).text
    assert p.json_mode is False  # запомнили: дальше без response_format
    assert p.ping() == (True, "ok")


def test_rate_limit_message_hides_key(server):
    server.mode = "rate_limit"
    p = OpenAICompatProvider("m", server.base, "gsk_secret", provider="groq")
    with pytest.raises(LLMUnavailable) as e:
        p.chat([{"role": "user", "content": "x"}])
    assert "лимит" in str(e.value) and "gsk_secret" not in str(e.value)


def test_gigachat_gets_token_once(server, monkeypatch):
    monkeypatch.setattr(openai_compat, "GIGACHAT_OAUTH_URL", server.base + "/oauth")
    p = OpenAICompatProvider("GigaChat-2", server.base, "authkey", provider="gigachat")
    p.chat([{"role": "user", "content": "x"}])
    p.chat([{"role": "user", "content": "y"}])
    oauth = [s for s in server.seen if s[0].endswith("/oauth")]
    assert len(oauth) == 1
    assert oauth[0][1]["Authorization"] == "Basic authkey" and oauth[0][1]["Rquid"]
    assert server.seen[-1][1]["Authorization"] == "Bearer tok-1"
