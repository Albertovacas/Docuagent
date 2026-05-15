import logging
import uuid
from datetime import datetime
from typing import List

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

from src.domain.documents import DocumentChunk
from src.domain.retrieval import SearchResult
from src.embeddings.fastembed_model import FastEmbedder
from src.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    REQUIRED_ENV_VARS = ["QDRANT_URL", "QDRANT_API_KEY"]
    COLLECTION_NAME = "docuagent_v1" # Nombre del proyecto

    def __init__(self, settings: Settings | None = None, embedder: FastEmbedder | None = None):
        self.settings = settings or get_settings()

        self.embedder = embedder or FastEmbedder(settings=self.settings)
        self.client = QdrantClient(
            url=self.settings.QDRANT_URL,
            api_key=self.settings.QDRANT_API_KEY,
        )
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        if not any(col.name == self.COLLECTION_NAME for col in collections):
            logger.info("Qdrant collection not found. Creating collection", extra={"collection": self.COLLECTION_NAME})
            # Obtener dimensión del embedding dinámicamente
            dim = self.embedder.dimension()
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            # Índices para búsqueda rápida por metadatos
            self.client.create_payload_index(self.COLLECTION_NAME, "page", PayloadSchemaType.INTEGER)
            self.client.create_payload_index(self.COLLECTION_NAME, "document_id", PayloadSchemaType.KEYWORD)

    def _point_id(self, doc) -> str:
        raw_id = "|".join(
            [
                str(doc.metadata.get("source", "")),
                str(doc.metadata.get("page", "")),
                str(doc.metadata.get("chunk_index", "")),
                doc.page_content,
            ]
        )
        return str(uuid.uuid5(uuid.NAMESPACE_URL, raw_id))

    def _chunk_point_id(self, chunk: DocumentChunk) -> str:
        """Generate deterministic point ID for a DocumentChunk."""
        raw_id = "|".join(
            [
                str(chunk.document_id or "unknown"),
                str(chunk.page or ""),
                str(chunk.chunk_index),
                chunk.text,
            ]
        )
        return str(uuid.uuid5(uuid.NAMESPACE_URL, raw_id))

    def upload_documents(self, documents):
        """
        Adapta los splits de LangChain a tu sistema de Qdrant.
        """
        points = []
        for doc in documents:
            embedding = self.embedder.embed_passage(doc.page_content)

            payload = {
                "text": doc.page_content,
                **doc.metadata,
                "timestamp": int(datetime.utcnow().timestamp()),
            }

            points.append(PointStruct(
                id=self._point_id(doc),
                vector=embedding.tolist(),
                payload=payload,
            ))

        self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)
        logger.info("Chunks uploaded to Qdrant", extra={"collection": self.COLLECTION_NAME, "point_count": len(points)})

    def search(self, query: str, k: int = 5) -> List[SearchResult]:
        query_vector = self.embedder.embed_query(query)

        results = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_vector.tolist(),
            limit=k,
        ).points

        return [
            SearchResult(
                text=hit.payload["text"],
                metadata={k: v for k, v in hit.payload.items() if k != "text"},
                score=hit.score,
            ) for hit in results
        ]
