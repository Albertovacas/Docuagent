from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from src.settings import Settings, get_settings


def get_llm(model_name="gemini-2.5-flash", temperature=0, settings: Settings | None = None):
    settings = settings or get_settings()

    if "gemini" in model_name:
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=settings.GOOGLE_API_KEY,
        )

    return ChatGroq(
        model_name=model_name,
        temperature=temperature,
        api_key=settings.GROQ_API_KEY,
    )
