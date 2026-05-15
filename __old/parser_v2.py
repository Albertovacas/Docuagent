import os
import base64
from pypdf import PdfReader
from pdf2image import convert_from_path
from docuagent.src.helpers.utils import get_llm
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

load_dotenv()

class HybridParser:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.llm = get_llm(model_name=model_name)
        
    def _is_complex(self, text):
        """Heurística de decisión: ¿Necesitamos visión?"""
        if not text or len(text.strip()) < 50: return True # Imagen o poco texto
        
        digits = sum(c.isdigit() for c in text)
        spaces = text.count("    ") # Detección de posibles columnas
        
        # Si >15% son dígitos o hay muchas tabulaciones de espacios
        if (digits / len(text)) > 0.15 or spaces > 5:
            return True
        return False

    def _encode_image(self, image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def parse_document(self, pdf_path):
        reader = PdfReader(pdf_path)
        full_content = []
        
        print(f"🧐 Iniciando análisis híbrido de: {os.path.basename(pdf_path)}")
        
        for i, page in enumerate(reader.pages):
            page_num = i + 1
            raw_text = page.extract_text()
            
            if self._is_complex(raw_text):
                print(f"  [Pág {page_num}] ✨ MODO VISIÓN: Detectada estructura compleja.")
                # Convertir a imagen y usar base64 para seguridad
                images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
                temp_path = f"data/temp_{page_num}.png"
                images[0].save(temp_path, "PNG")
                
                b64_img = self._encode_image(temp_path)
                msg = HumanMessage(content=[
                    {"type": "text", "text": "Extrae el texto y tablas de esta página en Markdown."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                ])
                res = self.llm.invoke([msg])
                content = res.content
                os.remove(temp_path)
            else:
                print(f"  [Pág {page_num}] 📝 MODO TEXTO: Extracción rápida.")
                content = raw_text
                
            full_content.append(f"## Página {page_num}\n\n{content}")
            
        return "\n\n".join(full_content)