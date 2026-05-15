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

Main modules:

- `src/ingestion/parser.py`: hybrid PDF parser.
- `src/database/vector_store.py`: chunking, embedding, Qdrant upload and search.
- `src/agents/retrieval_agent.py`: retrieval, reranking and answer generation.
- `src/helpers/utils.py`: LLM factory.
- `src/settings.py`: environment-based configuration.
- `src/observability/langfuse_config.py`: Langfuse callback factories.

## Setup

Install dependencies with `uv`:

```bash
uv sync
```

Create your local environment file:

```bash
cp .env.example .env
```

Fill in the required values in `.env`.

## Environment Variables

The project reads configuration from `.env` through Pydantic settings.

Required provider keys:

```env
GROQ_API_KEY=
TOGETHER_API_KEY=
GCP_PROJECT_ID=
GCP_REGION=
GOOGLE_API_KEY=
QDRANT_API_KEY=
QDRANT_URL=
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_BASE_URL=
```

Configurable model names:

```env
TEXT_MODEL_NAME=llama-3.3-70b-versatile
SMALL_TEXT_MODEL_NAME=gemma2-9b-it
STT_MODEL_NAME=whisper-large-v3-turbo
TTS_MODEL_NAME=eleven_flash_v2_5
TTI_MODEL_NAME=black-forest-labs/FLUX.1-schnell-Free
ITT_MODEL_NAME=meta-llama/llama-4-scout-17b-16e-instruct
EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-es
```

## CLI Usage

DocuAgent exposes a small CLI:

```bash
uv run docuagent --help
```

### Parse a PDF

```bash
uv run docuagent parse data/DeepSeek_V4.pdf data/DeepSeek_V4.md
```

This reads the PDF, decides page by page whether to use text extraction or vision OCR, and writes Markdown.

### Index Markdown

```bash
uv run docuagent index data/DeepSeek_V4.md
```

Optional chunking parameters:

```bash
uv run docuagent index data/DeepSeek_V4.md --chunk-size 800 --chunk-overlap 100
```

This chunks the Markdown, embeds each chunk, and uploads points to the configured Qdrant collection.

### Ask a Question

```bash
uv run docuagent ask "What are the main contributions of the document?"
```

Optional retrieval parameters:

```bash
uv run docuagent ask "What benchmarks are reported?" --k 20 --top-n 10
```

- `--k`: number of vector search candidates.
- `--top-n`: number of reranked chunks used as context.

## Logging

Runtime modules use standard Python logging. The CLI enables `INFO` logs by default.

Use `--verbose` for debug-level logs:

```bash
uv run docuagent --verbose ask "What is this document about?"
```

## Current Limitations

- There is no FastAPI service yet.
- Tests are still minimal and one existing test depends on external provider credentials.
- The Qdrant collection name is fixed as `docuagent_v1`.
- The project currently assumes a simple local workflow.
- There is no automated RAG evaluation dataset yet.
- The parser depends on external multimodal LLM calls for complex pages.
- Metadata is basic: source, page and chunk index.
- Multi-document lifecycle operations such as delete, reindex and versioning are not yet implemented.

## Roadmap

Near-term improvements:

- Add unit tests for metadata normalization, deterministic point IDs and retrieval context selection.
- Add an integration-test marker for provider-dependent tests.
- Add a FastAPI interface for question answering.
- Add RAG evaluation fixtures and metrics.
- Add Docker and CI.
- Add richer document metadata and document lifecycle operations.
- Add cost tracking for OCR, embeddings and answer generation.

## Strategic Notes

The repository includes a strategic improvement map at:

```text
docs/strategic_improvement_map.md
```

That document captures architecture, maintainability, scalability, observability, security, developer experience, RAG quality and deployment recommendations.
