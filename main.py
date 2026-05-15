import argparse
import logging
from pathlib import Path


def _configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _parse_document(args: argparse.Namespace) -> None:
    from src.ingestion.parser import HybridParser

    parser = HybridParser()
    output_path = parser.parse_document(args.pdf_path, args.output_md)
    print(output_path)


def _index_document(args: argparse.Namespace) -> None:
    from src.ingestion.chunker import MarkdownChunker
    from src.vectorstores.qdrant_store import QdrantVectorStore

    chunker = MarkdownChunker()
    vector_store = QdrantVectorStore()
    documents = chunker.chunk_file(
        args.markdown_path,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    vector_store.upload_documents(documents)
    print(f"Indexed {len(documents)} chunks from {args.markdown_path}")


def _ask_question(args: argparse.Namespace) -> None:
    from src.agents.retrieval_agent import RetrievalAgent

    agent = RetrievalAgent()
    answer = agent.answer(args.question, k=args.k, top_n=args.top_n)
    print(answer)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docuagent",
        description="Parse, index, and ask questions over documents.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse", help="Parse a PDF into Markdown.")
    parse_parser.add_argument("pdf_path", type=Path, help="Path to the source PDF.")
    parse_parser.add_argument("output_md", type=Path, help="Path where Markdown will be written.")
    parse_parser.set_defaults(func=_parse_document)

    index_parser = subparsers.add_parser("index", help="Chunk and upload a Markdown document to Qdrant.")
    index_parser.add_argument("markdown_path", type=Path, help="Path to the Markdown document.")
    index_parser.add_argument("--chunk-size", type=int, default=800, help="Maximum characters per chunk.")
    index_parser.add_argument("--chunk-overlap", type=int, default=100, help="Chunk overlap in characters.")
    index_parser.set_defaults(func=_index_document)

    ask_parser = subparsers.add_parser("ask", help="Ask a question against the indexed document collection.")
    ask_parser.add_argument("question", help="Question to answer.")
    ask_parser.add_argument("--k", type=int, default=20, help="Number of vector search candidates.")
    ask_parser.add_argument("--top-n", type=int, default=10, help="Number of reranked chunks to use.")
    ask_parser.set_defaults(func=_ask_question)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _configure_logging(verbose=args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
