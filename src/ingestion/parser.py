import os
import re
import base64
import logging
import tempfile
from pathlib import Path
from pypdf import PdfReader
from pdf2image import convert_from_path
from src.llms.factory import get_llm
from src.prompts.ingestion_prompts import OCR_MULTIMODAL_PROMPT
from langchain_core.messages import HumanMessage
from src.settings import Settings, get_settings

logger = logging.getLogger(__name__)

class HybridParser:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        # Usamos Gemini 2.5 Flash por su velocidad y bajo coste en visión
        self.llm = get_llm(model_name=self.settings.ITT_MODEL_NAME, settings=self.settings)

    def _clean_markdown(self, text):
            """Evita que datos sueltos se conviertan en encabezados que rompan el RAG."""
            # Si una línea empieza por # y tiene menos de 5 palabras, es sospechosa de ser un dato, no un título
            lines = text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                if line.startswith('#'):
                    line = line.replace('#', '')
                cleaned_lines.append(line)
                
            return '\n'.join(cleaned_lines)

    def _is_complex(self, text):
        """Heurística para detectar tablas y gráficos."""
        if not text or len(text.strip()) < 50: return True
        
        lines = text.split('\n')
        table_indicators = 0
        
        # 1. Palabras clave de estructura científica
        if re.search(r"(Table|Figure|Comparison|Benchmark)\s+\d+", text, re.I):
            table_indicators += 2
            
        # 2. Detección de filas de datos (múltiples decimales por línea)
        for line in lines:
            if len(re.findall(r"\d+\.\d+", line)) >= 3:
                table_indicators += 1
        
        digit_ratio = sum(c.isdigit() for c in text) / len(text)
        return table_indicators >= 2 or digit_ratio > 0.15
    
    def _encode_image(self, image_path):
            """Codifica la imagen a base64 para envío seguro a la API."""
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')

    def parse_document(self, pdf_path, output_md):
        """Recorre el PDF y decide el método para cada página."""
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        full_markdown = [f"# {os.path.basename(pdf_path)}\n"]
        
        logger.info("Starting hybrid parser", extra={"pdf_path": str(pdf_path), "total_pages": total_pages})

        with tempfile.TemporaryDirectory() as temp_dir:
            for i in range(total_pages):
                page_num = i + 1
                page = reader.pages[i]
                raw_text = page.extract_text()
                
                if self._is_complex(raw_text):
                #if False:
                    logger.info(
                        "Processing page with vision mode",
                        extra={"page": page_num, "total_pages": total_pages},
                    )
                    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
                    temp_path = Path(temp_dir) / f"temp_p{page_num}.png"
                    images[0].save(temp_path, "PNG")
                    
                    b64_img = self._encode_image(temp_path)
                    msg = HumanMessage(content=[
                        {"type": "text", "text": OCR_MULTIMODAL_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                    ])
                    res = self.llm.invoke([msg])
                    content = res.content
                else:
                    logger.info(
                        "Processing page with text mode",
                        extra={"page": page_num, "total_pages": total_pages},
                    )
                    content = raw_text

                clean_content = self._clean_markdown(content)

                # Añadimos el contenido al registro final
                full_markdown.append(f"## Página {page_num}\n\n{clean_content}\n")

        # Guardar el resultado final en un archivo Markdown
        with open(output_md, "w", encoding="utf-8") as f:
            f.write("\n".join(full_markdown))
        
        return output_md
