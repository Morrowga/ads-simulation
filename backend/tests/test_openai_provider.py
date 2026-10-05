"""OpenAI provider against a fake HTTP transport (no network, no API key)."""

from __future__ import annotations

import json

import httpx
from openai import AsyncOpenAI

from app.llm.openai_provider import OpenAIProvider

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


def _completion(body: dict) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": body["model"],
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps({"ok": True})},
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "total_tokens": 110,
            "prompt_tokens_details": {"cached_tokens": 80},
        },
    }


def _provider(handler) -> OpenAIProvider:  # noqa: ANN001
    p = OpenAIProvider()
    p.client = AsyncOpenAI(
        api_key="test", max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    return p


async def test_structured_output_and_usage() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json=_completion(body))

    res = await _provider(handler).complete_json(
        model="model-a",
        system="s",
        user="u",
        schema_name="t",
        schema=SCHEMA,
        temperature=0.9,
        images=None,
        context=None,
    )
    assert res.data == {"ok": True}
    assert res.input_tokens == 100 and res.cached_tokens == 80 and res.output_tokens == 10
    assert seen[0]["response_format"]["json_schema"]["strict"] is True
    assert seen[0]["temperature"] == 0.9


async def test_retries_without_temperature_when_model_rejects_it() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if "temperature" in body:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Unsupported value: 'temperature' does not support 0.9 with this "
                        "model. Only the default (1) value is supported.",
                        "type": "invalid_request_error",
                        "param": "temperature",
                        "code": "unsupported_value",
                    }
                },
            )
        return httpx.Response(200, json=_completion(body))

    p = _provider(handler)
    res = await p.complete_json(
        model="reasoning-model",
        system="s",
        user="u",
        schema_name="t",
        schema=SCHEMA,
        temperature=0.9,
        images=None,
        context=None,
    )
    assert res.data == {"ok": True}
    assert len(calls) == 2 and "temperature" not in calls[1]
    # the model is remembered: the next call goes straight through without temperature
    await p.complete_json(
        model="reasoning-model",
        system="s",
        user="u",
        schema_name="t",
        schema=SCHEMA,
        temperature=0.9,
        images=None,
        context=None,
    )
    assert len(calls) == 3 and "temperature" not in calls[2]
