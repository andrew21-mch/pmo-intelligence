import structlog
import httpx
from openai import AsyncOpenAI

from app.config import settings

logger = structlog.get_logger(__name__)

EMBED_DIM = 768  # nomic-embed-text


class EmbeddingService:
    async def embed(self, text: str) -> list[float]:
        if settings.llm_provider == "openai" and settings.openai_api_key:
            return await self._openai_embed(text)
        return await self._ollama_embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            results.append(await self.embed(text))
        return results

    async def _ollama_embed(self, text: str) -> list[float]:
        base = settings.ollama_base_url.replace("/v1", "").rstrip("/")
        model = settings.ollama_embed_model
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            if response.status_code >= 400:
                logger.warning("ollama_embed_failed", status=response.status_code, body=response.text[:200])
                return self._fallback_embed(text)
            data = response.json()
            embedding = data.get("embedding")
            if not embedding:
                return self._fallback_embed(text)
            return embedding

    async def _openai_embed(self, text: str) -> list[float]:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.embeddings.create(
            model=settings.openai_embed_model,
            input=text,
        )
        return response.data[0].embedding

    @staticmethod
    def _fallback_embed(text: str) -> list[float]:
        """Deterministic pseudo-embedding when Ollama embed model unavailable."""
        import hashlib

        vec = [0.0] * EMBED_DIM
        for i, token in enumerate(text.lower().split()):
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % EMBED_DIM] += 1.0 / (i + 1)
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]
