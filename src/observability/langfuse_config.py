from functools import lru_cache

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from src.settings import Settings, get_settings


@lru_cache
def _get_langfuse() -> Langfuse:
    settings = get_settings()

    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_BASE_URL
    )


def get_langfuse(settings: Settings | None = None) -> Langfuse:
    if settings is None:
        return _get_langfuse()

    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_BASE_URL
    )


@lru_cache
def get_langfuse_callback():
    return CallbackHandler()
