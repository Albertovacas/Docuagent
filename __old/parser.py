import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def process_pdf(file_path):
    """
    Carga un PDF y lo divide en fragmentos (chunks) siguiendo el ADR-004.
    """
    print(f"--- Procesando: {os.path.basename(file_path)} ---")
    
    # 1. Carga del documento
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    
    # 2. Configuración del Chunking (ADR-004: 10-15% overlap)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150, # 15% de solapamiento para mantener contexto[cite: 1]
        length_function=len,
    )
    
    chunks = text_splitter.split_documents(pages)
    print(f"✅ Documento procesado: {len(pages)} páginas -> {len(chunks)} fragmentos.")
    
    return chunks

if __name__ == "__main__":
    # Buscamos el primer PDF en la carpeta data/[cite: 1]
    data_dir = "data"
    pdf_files = [f for f in os.listdir(data_dir) if f.endswith('.pdf')]
    
    if pdf_files:
        sample_path = os.path.join(data_dir, pdf_files[0])
        resultado = process_pdf(sample_path)
        # Mostramos un ejemplo del primer chunk
        if resultado:
            print(f"\nEjemplo del primer fragmento:\n{resultado[0].page_content[:200]}...")
    else:
        print("❌ No se encontraron archivos PDF en la carpeta 'data/'.")