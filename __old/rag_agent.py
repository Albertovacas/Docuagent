import os
from src.helpers.utils import get_llm
from src.database.vector_store import VectorStore
from src.prompts.rag_prompts import RAG_SYSTEM_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage
from src.settings import settings

class RAGAgent:
    def __init__(self):
        self.vector_store = VectorStore()
        self.llm = get_llm(model_name=settings.TEXT_MODEL_NAME) # Flash es ideal por su baja latencia

    def answer(self, question: str, k: int = 10):
        # 1. Recuperación (Retrieval)
        print(f"🔍 Buscando contexto para: '{question}'...")
        memories = self.vector_store.search(question, k=k)

        for i, res in enumerate(memories):
            print(f"📍 Resultado {i+1} (Score: {res.score:.4f})")
            print(f"📄 Ubicación: {res.metadata.get('Pagina', 'Desconocida')}")
            print(f"📝 Texto:\n{res.text}")
            print("-" * 50)
                
        # 2. Construcción del contexto
        context_text = ""
        for mem in memories:
            page_info = mem.metadata.get('Pagina', 'Página desconocida')
            context_text += f"--- Inicio Fragmento ({page_info}) ---\n{mem.text}\n--- Fin Fragmento ---\n\n"

        # 3. Preparación de mensajes para el LLM
        prompt_filled = RAG_SYSTEM_PROMPT.format(context=context_text)
        
        messages = [
            SystemMessage(content=prompt_filled),
            HumanMessage(content=question)
        ]

        # 4. Generación
        print("🧠 Generando respuesta...")
        response = self.llm.invoke(messages)
        
        return response.content