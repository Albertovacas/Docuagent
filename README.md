# DocuAgent

DocuAgent is a document RAG prototype for technical PDFs. It parses documents into Markdown, chunks and indexes them in Qdrant, retrieves relevant passages, reranks them, and generates grounded answers with an LLM.

The project is currently focused on a local developer workflow, not yet a production API.

## What It Does

- Parses PDFs with a hybrid strategy:
  - regular text extraction for simple pages
  - multimodal OCR for complex pages with tables or charts
- Converts parsed output into Markdown.
- Splits Markdown into chunks with page metadata.
- Stores embeddings in Qdrant.
- Performs vector search plus reranking.
- Generates answers using retrieved context.
- Emits runtime logs through Python logging.
- Supports Langfuse callbacks for LLM traces.

## Architecture

```text
PDF
  -> HybridParser
  -> Markdown
  -> VectorStore chunking
  -> Qdrant

Question
  -> RetrievalAgent
  -> Vector search
  -> Rerank
  -> LLM answer
```