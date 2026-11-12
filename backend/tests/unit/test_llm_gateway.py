"""complete_json: разбор JSON, повтор при ошибке, журнал вызовов."""

import pytest
from pydantic import BaseModel

from app.llm.base import LLMError, complete_json, extract_json
from app.llm.fake import FakeLLM
from app.llm.prompts import load_prompt, render


class Out(BaseModel):
    value: int


def test_extract_json_from_fenced_block():
    assert extract_json('```json\n{"value": 1}\n```') == '{"value": 1}'


def test_retry_after_invalid_json_and_log():
    llm = FakeLLM(["не json", {"value": 7}])
    log = []
    out = complete_json(
        llm, [{"role": "user", "content": "x"}], Out, purpose="t", prompt_version="t.v1", log=log
    )
    assert out.value == 7
    assert log[0].valid_json and log[0].attempts == 2
    # при повторе модели показывают её ошибку
    assert "не соответствует схеме" in llm.requests[1][-1]["content"]


def test_gives_up_after_retries():
    llm = FakeLLM(default="{}")
    log = []
    with pytest.raises(LLMError):
        complete_json(llm, [], Out, purpose="t", prompt_version="v", log=log, retries=2)
    assert len(llm.requests) == 3 and not log[0].valid_json


def test_prompts_load_and_render():
    p = load_prompt("analyze_answer", "v2")
    assert p.system and "{{answer}}" in p.user
    assert "Привет" in render("{{a}} {b}", a="Привет")
    assert render("{{a}} {b}", a="x").endswith("{b}")
