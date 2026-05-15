from fastembed import TextEmbedding

from src.settings import Settings, get_settings


class FastEmbedder:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.model = TextEmbedding(self.settings.EMBEDDING_MODEL)

    def dimension(self) -> int:
        return len(self.embed_text("test"))

    def embed_text(self, text: str):
        return list(self.model.embed([text]))[0]

    def embed_passage(self, text: str):
        return self.embed_text(f"passage: {text}")

    def embed_query(self, query: str):
        return self.embed_text(f"query: {query}")
