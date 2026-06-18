from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.document_service import DocumentService
from app.services.governance_sample import SAMPLE_GOVERNANCE_DOC
from app.services.rag import RAGService

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentOut(BaseModel):
    id: int
    filename: str
    title: str
    doc_type: str
    project_key: str | None
    chunk_count: int
    uploaded_at: str


class RAGSearchResult(BaseModel):
    score: float
    text: str
    title: str
    doc_type: str
    doc_id: int | None


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    doc_type: str = Form("governance"),
    project_key: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    content = (await file.read()).decode("utf-8", errors="replace")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Empty document")

    service = DocumentService(db)
    doc = await service.upload(
        filename=file.filename or "document.txt",
        content=content,
        title=title or None,
        doc_type=doc_type,
        project_key=project_key or None,
    )
    return _doc_out(doc)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    project_key: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[DocumentOut]:
    docs = await DocumentService(db).list_documents(project_key)
    return [_doc_out(d) for d in docs]


@router.post("/seed-governance", response_model=DocumentOut)
async def seed_governance(
    project_key: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    service = DocumentService(db)
    doc = await service.upload(
        filename="pmo-governance-manual.md",
        content=SAMPLE_GOVERNANCE_DOC,
        title="PMO Governance Manual",
        doc_type="governance",
        project_key=project_key or None,
    )
    return _doc_out(doc)


@router.get("/search", response_model=list[RAGSearchResult])
async def search_documents(
    q: str,
    limit: int = 5,
    project_key: str | None = None,
) -> list[RAGSearchResult]:
    rag = RAGService()
    hits = await rag.search(q, limit=limit, project_key=project_key)
    return [RAGSearchResult(**h) for h in hits]


def _doc_out(doc) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        title=doc.title,
        doc_type=doc.doc_type,
        project_key=doc.project_key,
        chunk_count=doc.chunk_count,
        uploaded_at=doc.uploaded_at.isoformat() if doc.uploaded_at else "",
    )
