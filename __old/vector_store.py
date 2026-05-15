import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams, PayloadSchemaType
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from fastembed import TextEmbedding

@dataclass
class Memory:
    text: str
    metadata: dict
    score: Optional[float] = None
    # Añadimos helper para ver la página rápido
    @property
    def page(self) -> str:
        return self.metadata.get("page", "N/A")

class VectorStore:
    REQUIRED_ENV_VARS = ["QDRANT_URL", "QDRANT_API_KEY"]
    EMBEDDING_MODEL = "jinaai/jina-embeddings-v2-base-es"
    COLLECTION_NAME = "docuagent_v1" # Nombre del proyecto
    
    _instance: Optional["VectorStore"] = None
    _initialized: bool = False

    def __new__(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self,
                 data_path: str) -> None:
        if not self._initialized:
            self.model = TextEmbedding(self.EMBEDDING_MODEL)
            self.client = QdrantClient(
                url=os.getenv("QDRANT_URL"),
                api_key=os.getenv("QDRANT_API_KEY"),
            )
            self._ensure_collection()
            self._initialized = True

            with open(data_path, "r", encoding="utf-8") as f:
                self.text = f.read()


    def _ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        if not any(col.name == self.COLLECTION_NAME for col in collections):
            # Obtener dimensión del embedding dinámicamente
            dim = len(list(self.model.embed(["test"]))[0])
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            # Índices para búsqueda rápida por metadatos
            self.client.create_payload_index(self.COLLECTION_NAME, "page", PayloadSchemaType.INTEGER)

    def chunk_documents(self, chunk_size: int = 800, chunk_overlap: int = 100):

        headers_to_split_on = [("#", "Archivo"), ("##", "Pagina")]
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        md_header_splits = markdown_splitter.split_text(self.text)

        # 3. División final en trozos manejables
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.documents = text_splitter.split_documents(md_header_splits)

        print(f"📄 Markdown cargado. Tenemos {len(self.documents)} fragmentos listos para vectorizar.")


    def upload_documents(self):
        """
        Adapta los splits de LangChain a tu sistema de Qdrant.
        """
        points = []
        for doc in self.documents:
            # Importante: E5 requiere el prefijo 'passage: ' para guardar
            embedding = list(self.model.embed([f"passage: {doc.page_content}"]))[0]
            
            payload = {
                "text": doc.page_content,
                **doc.metadata,
                "timestamp": int(datetime.utcnow().timestamp())
            }
            
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding.tolist(),
                payload=payload
            ))
        
        self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)
        print(f"✅ {len(points)} fragmentos subidos a Qdrant.")

    def search(self, query: str, k: int = 5) -> List[Memory]:
        # E5 requiere prefijo 'query: ' para buscar
        query_vector = list(self.model.embed([f"query: {query}"]))[0]
        
        results = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_vector.tolist(),
            limit=k,
        ).points

        return [
            Memory(
                text=hit.payload["text"],
                metadata={k: v for k, v in hit.payload.items() if k != "text"},
                score=hit.score
            ) for hit in results
        ]