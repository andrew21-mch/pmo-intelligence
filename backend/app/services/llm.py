import json
import re

import httpx
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings

logger = structlog.get_logger(__name__)

_OLLAMA_JSON_HINTS: dict[str, str] = {
    "StatusLLMOutput": (
        'Return JSON only: {"executive_summary": "2-3 sentence summary", '
        '"recommendations": ["action 1", "action 2"]}'
    ),
    "RiskLLMOutput": (
        'Return JSON only: {"reasoning": "2-3 sentence risk analysis", '
        '"recommended_actions": ["action 1", "action 2"]}'
    ),
    "MeetingLLMOutput": (
        'Return JSON only with keys: summary, action_items (array of {description, assignee}), '
        "decisions (array of {description}), risks_identified (array of {description, severity})."
    ),
}


class LLMService:
    """LLM client — supports local Ollama (OpenAI-compatible) or OpenAI."""

    def __init__(self) -> None:
        self.model = settings.llm_model
        self._client: AsyncOpenAI | None = None

    @property
    def is_configured(self) -> bool:
        if settings.llm_provider == "ollama":
            return True
        return bool(settings.openai_api_key)

    @property
    def client(self) -> AsyncOpenAI:
        if not self.is_configured:
            raise RuntimeError("LLM not configured")

        if self._client is None:
            timeout = httpx.Timeout(settings.ollama_llm_timeout_seconds, connect=10.0)
            if settings.llm_provider == "ollama":
                self._client = AsyncOpenAI(
                    base_url=settings.ollama_base_url,
                    api_key="ollama",
                    timeout=timeout,
                )
            else:
                self._client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout)

        return self._client

    async def structured_completion(
        self, *, system: str, user: str, schema: type[BaseModel]
    ) -> BaseModel:
        try:
            return await self._structured_completion(system=system, user=user, schema=schema)
        except Exception as exc:
            logger.warning("llm_failed", provider=settings.llm_provider, model=self.model, error=str(exc))
            raise

    async def try_structured_completion(
        self, *, system: str, user: str, schema: type[BaseModel]
    ) -> BaseModel | None:
        try:
            return await self._structured_completion(system=system, user=user, schema=schema)
        except Exception as exc:
            logger.warning("llm_failed_using_fallback", provider=settings.llm_provider, error=str(exc))
            return None

    async def _structured_completion(
        self, *, system: str, user: str, schema: type[BaseModel]
    ) -> BaseModel:
        if settings.llm_provider == "openai" and settings.openai_api_key:
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format=schema,
            )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                raise RuntimeError("LLM returned empty structured response")
            logger.info("llm_completion", provider="openai", model=self.model, schema=schema.__name__)
            return parsed

        json_hint = _OLLAMA_JSON_HINTS.get(
            schema.__name__,
            f"Return JSON only with these fields: {', '.join(schema.model_fields.keys())}.",
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": f"{system}\n\n{json_hint}\nDo not return a JSON schema — return actual data values.",
                },
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("LLM returned empty response")
        parsed = _parse_ollama_json(content, schema)
        logger.info("llm_completion", provider=settings.llm_provider, model=self.model, schema=schema.__name__)
        return parsed


def _parse_ollama_json(content: str, schema: type[BaseModel]) -> BaseModel:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")

    # Ollama sometimes echoes the JSON schema instead of filling values
    if "properties" in data and "type" in data and not _has_schema_fields(data, schema):
        raise ValueError("LLM returned JSON schema instead of data")

    return schema.model_validate(data)


def _has_schema_fields(data: dict, schema: type[BaseModel]) -> bool:
    return any(field in data for field in schema.model_fields)
