from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class DocumentStatus(str, Enum):
    """Lifecycle states for document ingestion."""

    PENDING = "pending"
    INGESTING = "ingesting"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


@dataclass
class Document:
    document_id: str
    source: str
    content_hash: str
    status: DocumentStatus = DocumentStatus.PENDING
    version: int = 1
    ingestion_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    chunks_count: int = 0


@dataclass
class DocumentChunk:
    text: str
    source: str | None
    page: int | None
    chunk_index: int
    document_id: str | None = None
