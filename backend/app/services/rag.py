import uuid

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from app.config import settings
from app.services.embeddings import EMBED_DIM, EmbeddingService

logger = structlog.get_logger(__name__)


class RAGService:
    def __init__(self) -> None:
        self.client = QdrantClient(url=settings.qdrant_url)
        self.collection = settings.qdrant_collection
        self.embedder = EmbeddingService()

    def ensure_collection(self) -> None:
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection not in collections:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
            )
            logger.info("qdrant_collection_created", collection=self.collection)

    async def index_document(
        self,
        *,
        doc_id: int,
        title: str,
        doc_type: str,
        project_key: str | None,
        chunks: list[str],
    ) -> int:
        self.ensure_collection()
        points: list[PointStruct] = []
        embeddings = await self.embedder.embed_batch(chunks)

        for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"doc-{doc_id}-chunk-{idx}")),
                    vector=vector,
                    payload={
                        "doc_id": doc_id,
                        "chunk_index": idx,
                        "text": chunk,
                        "title": title,
                        "doc_type": doc_type,
                        "project_key": project_key or "",
                    },
                )
            )

        self.client.upsert(collection_name=self.collection, points=points)
        return len(points)

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        doc_type: str | None = None,
        project_key: str | None = None,
    ) -> list[dict]:
        self.ensure_collection()
        vector = await self.embedder.embed(query)

        conditions = []
        if doc_type:
            conditions.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
        if project_key:
            conditions.append(FieldCondition(key="project_key", match=MatchValue(value=project_key)))

        query_filter = Filter(must=conditions) if conditions else None

        results = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=query_filter,
            limit=limit,
        )

        return [
            {
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "title": hit.payload.get("title", ""),
                "doc_type": hit.payload.get("doc_type", ""),
                "doc_id": hit.payload.get("doc_id"),
                "chunk_index": hit.payload.get("chunk_index"),
            }
            for hit in results
        ]

    def delete_document_vectors(self, doc_id: int) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )
