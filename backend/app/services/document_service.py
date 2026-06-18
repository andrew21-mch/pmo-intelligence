from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentModel
from app.services.chunking import chunk_text
from app.services.rag import RAGService


class DocumentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.rag = RAGService()

    async def upload(
        self,
        *,
        filename: str,
        content: str,
        title: str | None = None,
        doc_type: str = "governance",
        project_key: str | None = None,
    ) -> DocumentModel:
        chunks = chunk_text(content)
        doc = DocumentModel(
            filename=filename,
            title=title or filename,
            doc_type=doc_type,
            project_key=project_key.upper() if project_key else None,
            chunk_count=len(chunks),
            content_preview=content[:500],
        )
        self.db.add(doc)
        await self.db.flush()

        indexed = await self.rag.index_document(
            doc_id=doc.id,
            title=doc.title,
            doc_type=doc_type,
            project_key=doc.project_key,
            chunks=chunks,
        )
        doc.chunk_count = indexed
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def list_documents(self, project_key: str | None = None) -> list[DocumentModel]:
        query = select(DocumentModel).order_by(DocumentModel.uploaded_at.desc())
        if project_key:
            query = query.where(
                (DocumentModel.project_key == project_key.upper()) | (DocumentModel.project_key.is_(None))
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get(self, doc_id: int) -> DocumentModel | None:
        result = await self.db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
        return result.scalar_one_or_none()
