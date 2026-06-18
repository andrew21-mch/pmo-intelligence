import json

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings

logger = structlog.get_logger(__name__)


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
            if settings.llm_provider == "ollama":
                self._client = AsyncOpenAI(
                    base_url=settings.ollama_base_url,
                    api_key="ollama",
                )
            else:
                self._client = AsyncOpenAI(api_key=settings.openai_api_key)

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

        schema_hint = json.dumps(schema.model_json_schema(), indent=2)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{system}\n\n"
                        "Respond with valid JSON only, no markdown, matching this schema:\n"
                        f"{schema_hint}"
                    ),
                },
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("LLM returned empty response")
        logger.info("llm_completion", provider=settings.llm_provider, model=self.model, schema=schema.__name__)
        return schema.model_validate_json(content)
