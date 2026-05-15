import re

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


class MarkdownChunker:
    def _normalize_metadata(self, metadata: dict) -> dict:
        page = metadata.get("page") or metadata.get("Pagina")
        page_number = None

        if isinstance(page, int):
            page_number = page
        elif isinstance(page, str):
            match = re.search(r"\d+", page)
            if match:
                page_number = int(match.group())

        return {
            **metadata,
            "source": metadata.get("source") or metadata.get("Archivo"),
            "page": page_number,
        }

    def chunk_file(self, data_path, chunk_size: int = 800, chunk_overlap: int = 100):
        with open(data_path, "r", encoding="utf-8") as f:
            text = f.read()

        headers_to_split_on = [("#", "source"), ("##", "page")]
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        md_header_splits = markdown_splitter.split_text(text)

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        documents = text_splitter.split_documents(md_header_splits)
        for chunk_index, doc in enumerate(documents):
            doc.metadata = {
                **self._normalize_metadata(doc.metadata),
                "chunk_index": chunk_index,
            }

        return documents
