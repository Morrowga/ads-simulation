"""OpenAI provider: official async SDK, strict JSON-schema structured outputs, vision input, transcription."""

from __future__ import annotations

import base64
import io
import json
import time
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

from app.config import get_settings
from app.llm.client import ProviderResult, RetryableError


class OpenAIProvider:
    name = "openai"
    # models that rejected a non-default temperature (shared across instances for the process lifetime)
    _no_temperature_models: set[str] = set()

    def __init__(self) -> None:
        s = get_settings()
        self.client = AsyncOpenAI(api_key=s.OPENAI_API_KEY or "missing", timeout=90.0, max_retries=0)

    @staticmethod
    def _image_part(data: bytes) -> dict[str, Any]:
        mime = "image/jpeg"
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        elif data[:4] == b"RIFF":
            mime = "image/webp"
        b64 = base64.b64encode(data).decode("ascii")
        return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "low"}}

    async def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float,
        images: list[bytes] | None,
        context: dict[str, Any] | None,
    ) -> ProviderResult:
        user_content: Any = user
        if images:
            user_content = [{"type": "text", "text": user}] + [self._image_part(img) for img in images[:16]]
        t0 = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
        }
        # Some newer (reasoning) models only accept the default temperature. Send it when the model
        # supports it; if the API rejects it, remember that for this model and retry without it.
        if model not in self._no_temperature_models:
            kwargs["temperature"] = temperature
        try:
            try:
                resp = await self.client.chat.completions.create(**kwargs)
            except APIStatusError as exc:
                if exc.status_code == 400 and "temperature" in str(exc).lower() and "temperature" in kwargs:
                    self._no_temperature_models.add(model)
                    kwargs.pop("temperature")
                    resp = await self.client.chat.completions.create(**kwargs)
                else:
                    raise
        except (RateLimitError, APIConnectionError, APITimeoutError) as exc:
            raise RetryableError(str(exc)) from exc
        except APIStatusError as exc:
            if exc.status_code >= 500:
                raise RetryableError(str(exc)) from exc
            raise
        latency = int((time.perf_counter() - t0) * 1000)
        usage = resp.usage
        cached = 0
        if usage is not None and getattr(usage, "prompt_tokens_details", None) is not None:
            cached = int(getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0)
        text = (resp.choices[0].message.content or "") if resp.choices else ""
        data: dict[str, Any] | None
        invalid = False
        try:
            data = json.loads(text) if text else None
            if not isinstance(data, dict):
                data, invalid = None, True
        except json.JSONDecodeError:
            data, invalid = None, True
        if resp.choices and resp.choices[0].finish_reason == "content_filter":
            data, invalid = None, True
        return ProviderResult(
            data=data,
            text=text,
            input_tokens=int(usage.prompt_tokens) if usage else 0,
            cached_tokens=cached,
            output_tokens=int(usage.completion_tokens) if usage else 0,
            latency_ms=latency,
            model=resp.model or model,
            invalid_json=invalid,
        )

    async def transcribe(self, *, model: str, audio: bytes, mime: str) -> ProviderResult:
        t0 = time.perf_counter()
        buf = io.BytesIO(audio)
        buf.name = "audio.mp3" if "mp" in mime else "audio.wav"
        try:
            resp = await self.client.audio.transcriptions.create(
                model=model, file=buf, response_format="json"
            )
        except (RateLimitError, APIConnectionError, APITimeoutError) as exc:
            raise RetryableError(str(exc)) from exc
        except APIStatusError as exc:
            if exc.status_code >= 500:
                raise RetryableError(str(exc)) from exc
            raise
        text = getattr(resp, "text", "") or ""
        # transcription endpoints report duration rather than tokens; approximate input tokens from audio seconds
        return ProviderResult(
            data={"text": text},
            text=text,
            input_tokens=max(1, len(audio) // 4000),
            output_tokens=max(1, len(text) // 4),
            latency_ms=int((time.perf_counter() - t0) * 1000),
            model=model,
        )
