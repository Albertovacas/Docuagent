import logging
import time

from flashrank import Ranker, RerankRequest
from langchain_core.messages import SystemMessage, HumanMessage
from langfuse import observe
from src.llms.factory import get_llm
from src.vectorstores.qdrant_store import QdrantVectorStore
from src.prompts.rag_prompts import RAG_SYSTEM_PROMPT
from src.settings import Settings, get_settings
from src.observability.langfuse_config import get_langfuse_callback

logger = logging.getLogger(__name__)

def _unique_metadata_values(items, key: str):
    values = []
    seen = set()
    for item in items:
        value = item.metadata.get(key)
        if value is not None and value not in seen:
            values.append(value)
            seen.add(value)
    return values


def _unique_ranked_metadata_values(items, key: str):
    values = []
    seen = set()
    for item in items:
        value = item.get("meta", {}).get(key)
        if value is not None and value not in seen:
            values.append(value)
            seen.add(value)
    return values


class RetrievalAgent:

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.vector_store = QdrantVectorStore(settings=self.settings)
        self.llm = get_llm(model_name=self.settings.TEXT_MODEL_NAME, settings=self.settings) # Flash es ideal por su baja latencia
        self.ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")

    @observe(name="Vector Search")
    def _vector_search(self, question, k):
        return self.vector_store.search(question, k=k)
    
    @observe(name="Rerank")
    def _rerank(self, question, passages):

        rerank_request = RerankRequest(
            query=question,
            passages=passages
        )

        return self.ranker.rerank(rerank_request)

    @observe(name="Retrieval & Reranking")
    def _get_context(self, question:str, k: int = 20, top_n: int = 10):

        vector_search_started_at = time.perf_counter()
        search_results = self._vector_search(question, k=k)
        vector_search_latency_ms = (time.perf_counter() - vector_search_started_at) * 1000

        logger.info(
            "Vector search completed",
            extra={
                "retrieved_count": len(search_results),
                "pages": _unique_metadata_values(search_results, "page"),
                "sources": _unique_metadata_values(search_results, "source"),
                "scores": [result.score for result in search_results],
                "latency_ms": round(vector_search_latency_ms, 2),
            },
        )

        passages = [
            {
                "id": i, 
                "text": result.text, 
                "meta": {**result.metadata, "original_score": result.score}
            } 
            for i, result in enumerate(search_results)
        ]
        
        # 4. RE-RANKING: El momento de la verdad
        logger.info("Reranking candidates", extra={"candidate_count": len(passages)})
        rerank_started_at = time.perf_counter()
        ranked_results = self._rerank(question, passages)
        rerank_latency_ms = (time.perf_counter() - rerank_started_at) * 1000

        selected_results = ranked_results[:top_n]
        logger.info(
            "Rerank completed",
            extra={
                "reranked_count": len(ranked_results),
                "selected_count": len(selected_results),
                "selected_pages": _unique_ranked_metadata_values(selected_results, "page"),
                "selected_sources": _unique_ranked_metadata_values(selected_results, "source"),
                "selected_scores": [result.get("score") for result in selected_results],
                "selected_original_scores": [
                    result.get("meta", {}).get("original_score") for result in selected_results
                ],
                "latency_ms": round(rerank_latency_ms, 2),
            },
        )

        context_text = ""
        context_build_started_at = time.perf_counter()
        for mem in selected_results:
            page_info = mem.get('meta', {}).get('page', 'Página desconocida')
            context_text += f"--- Inicio Fragmento ({page_info}) ---\n{mem.get('text', '')}\n--- Fin Fragmento ---\n\n"
        context_build_latency_ms = (time.perf_counter() - context_build_started_at) * 1000

        logger.info(
            "Context built",
            extra={
                "context_chars": len(context_text),
                "context_fragments": len(selected_results),
                "top_n": top_n,
                "latency_ms": round(context_build_latency_ms, 2),
            },
        )

        return context_text
    
    @observe(name="DocuAgent")
    def answer(self, question: str, k: int = 20, top_n: int = 10) -> str:

        answer_started_at = time.perf_counter()
        langfuse_handler = get_langfuse_callback()

        # 1. Recuperación (Retrieval)
        logger.info(
            "Answer started",
            extra={
                "question": question,
                "k": k,
                "top_n": top_n,
                "model": self.settings.TEXT_MODEL_NAME,
            },
        )

        context_started_at = time.perf_counter()
        context_text = self._get_context(question, k=k, top_n=top_n)
        context_latency_ms = (time.perf_counter() - context_started_at) * 1000
        # 3. Preparación de mensajes para el LLM
        prompt_filled = RAG_SYSTEM_PROMPT.format(context=context_text)
        
        messages = [
            SystemMessage(content=prompt_filled),
            HumanMessage(content=question)
        ]

        # 4. Generación
        logger.info(
            "Generating answer",
            extra={
                "model": self.settings.TEXT_MODEL_NAME,
                "context_chars": len(context_text),
                "context_latency_ms": round(context_latency_ms, 2),
            },
        )
        generation_started_at = time.perf_counter()
        response = self.llm.invoke(
            messages, 
            config={"callbacks": [langfuse_handler]}
        )
        generation_latency_ms = (time.perf_counter() - generation_started_at) * 1000
        total_latency_ms = (time.perf_counter() - answer_started_at) * 1000

        logger.info(
            "Answer generated",
            extra={
                "model": self.settings.TEXT_MODEL_NAME,
                "answer_chars": len(response.content),
                "generation_latency_ms": round(generation_latency_ms, 2),
                "total_latency_ms": round(total_latency_ms, 2),
            },
        )
        
        return response.content
