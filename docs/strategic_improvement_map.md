# Mapa Estrategico de Mejoras - DocuAgent

Fecha de analisis: 2026-05-12

## Resumen ejecutivo

DocuAgent esta en una fase clara de prototipo tecnico: ya contiene las piezas nucleares de un sistema RAG documental, ingestion PDF/OCR, vector store en Qdrant, reranking, prompts y trazas con Langfuse. La idea es buena y el stack elegido es razonable para iterar rapido.

El principal riesgo no esta en una funcion aislada, sino en que el proyecto todavia no tiene fronteras arquitectonicas ni contratos operativos suficientes para convertirse en un producto fiable. La ingesta, recuperacion, configuracion, observabilidad y ejecucion viven acopladas a proveedores concretos, estado mutable local y scripts exploratorios.

Prioridad estrategica:

1. Corregir bugs funcionales que afectan directamente a calidad RAG.
2. Separar dominio, infraestructura y aplicacion.
3. Convertir notebooks y pruebas manuales en pipelines reproducibles.
4. Introducir evaluacion RAG automatizada y observabilidad de negocio.
5. Preparar despliegue, seguridad y control de coste.

## Lectura del estado actual

### Fortalezas

- El dominio del producto esta bien enfocado: extraccion documental, indexacion y pregunta-respuesta sobre documentos.
- Hay una estrategia hibrida de parsing: texto rapido para paginas simples y vision para paginas complejas.
- Se usa vector database externa, Qdrant, en lugar de almacenamiento improvisado.
- El pipeline contempla reranking con FlashRank, buena decision para mejorar precision sin depender solo de similitud vectorial.
- Langfuse ya esta presente, lo que permite evolucionar hacia observabilidad seria.
- El repositorio tiene `uv.lock`, lo que ayuda a reproducibilidad.

### Debilidades sistemicas

- El entrypoint real no existe: [main.py](/Users/albertovacas/Desktop/ai_projects/docuagent/main.py:1) solo imprime un saludo.
- El README esta vacio, por lo que no hay contrato de instalacion, uso, arquitectura ni decisiones.
- Tests no ejecutan correctamente: [tests/test_gcp.py](/Users/albertovacas/Desktop/ai_projects/docuagent/tests/test_gcp.py:1) importa `docuagent.src...`, pero el paquete actual expone `src...`.
- `.env` no esta ignorado en [.gitignore](/Users/albertovacas/Desktop/ai_projects/docuagent/.gitignore:1), aunque el proyecto depende de multiples secretos.
- `__old/`, notebooks, datos y codigo runtime conviven sin politica clara de ciclo de vida.
- No hay API, CLI funcional, job de ingesta, dockerizacion, CI, evaluaciones ni despliegue.

## Hallazgos criticos

### 1. Bug severo en construccion de contexto RAG

En [src/agents/retrieval_agent.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/agents/retrieval_agent.py:55), `_get_context` devuelve `context_text[:top_n]`. Eso corta caracteres, no resultados. Con `top_n=10`, el LLM recibe solo los primeros 10 caracteres del contexto.

Impacto:

- Respuestas pobres o alucinadas aunque la busqueda encuentre buenos fragmentos.
- Observabilidad enganosa: el retrieval puede parecer correcto, pero la generacion recibe contexto inutil.
- Cualquier benchmark RAG actual quedaria contaminado.

Mejora:

- Aplicar `ranked_results[:top_n]` antes de construir el texto.
- Introducir un presupuesto de tokens/caracteres independiente, por ejemplo `max_context_chars`.
- Devolver tambien fuentes estructuradas, no solo texto concatenado.

### 2. Metadata inconsistente entre indexacion y recuperacion

En [src/database/vector_store.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/database/vector_store.py:45) se crea indice para `page`, pero el splitter genera metadata `Pagina` en [src/database/vector_store.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/database/vector_store.py:52). Luego el agente lee `Pagina` en [src/agents/retrieval_agent.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/agents/retrieval_agent.py:52).

Impacto:

- Indices de payload inutiles.
- Filtros por pagina/documento fragiles o inexistentes.
- Citas inconsistentes.

Mejora:

- Definir un schema unico de chunk: `document_id`, `source_path`, `page`, `section`, `chunk_index`, `content_hash`, `ingested_at`.
- Normalizar metadata en ingesta, no en retrieval.
- Crear indices Qdrant sobre campos reales.

### 3. Configuracion import-time con secretos obligatorios

[src/settings.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/settings.py:30) instancia `Settings()` al importar el modulo. Muchos campos son obligatorios aunque no todos los comandos los necesiten.

Impacto:

- Tests unitarios y tooling fallan si falta cualquier secreto.
- Es dificil ejecutar parsing local sin Qdrant/Langfuse/Groq.
- Acopla todos los subsistemas al entorno completo.

Mejora:

- Mover `settings = Settings()` a una factory cacheada.
- Agrupar configuracion por dominio: `LLMSettings`, `VectorSettings`, `ObservabilitySettings`.
- Hacer opcionales los providers no usados por cada flujo.
- Validar al arrancar cada comando, no al importar librerias.

### 4. Abstraccion de modelos demasiado implicita

[src/helpers/utils.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/helpers/utils.py:7) decide proveedor si el nombre contiene `gemini`; si no, usa Groq.

Impacto:

- Modelos de Together, Vertex o futuros proveedores quedan mal enrutados.
- Cambiar nombres de modelos puede cambiar comportamiento de forma silenciosa.
- No hay timeouts, retries, limites de coste, callbacks comunes ni politicas por tarea.

Mejora:

- Crear un `LLMClientFactory` con provider explicito: `google_genai`, `groq`, `vertex`, `together`.
- Separar modelos por tarea: extraction, answer, rewrite, judge, embedding.
- Centralizar timeouts, retries, rate limits y tags de observabilidad.

### 5. Ingesta no idempotente ni robusta

En [src/database/vector_store.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/database/vector_store.py:79), cada chunk recibe `uuid4`, por lo que reingestar el mismo documento duplica puntos. `upload_documents` depende de `self.documents` creado previamente en [src/database/vector_store.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/database/vector_store.py:58).

Impacto:

- Coste y ruido crecientes en Qdrant.
- Dificultad para borrar/reindexar un documento.
- No hay control de versiones de documento ni deduplicacion.

Mejora:

- IDs deterministas: hash de `document_id + page + chunk_index + content_hash`.
- Separar `chunk_documents` como funcion pura que devuelve chunks.
- `upload_documents(chunks)` debe recibir input explicito.
- Registrar estado de ingesta por documento.

### 6. Parser con I/O temporal inseguro y limpieza destructiva

En [src/ingestion/parser.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/ingestion/parser.py:73) se escribe `data/temp_p{page}.png`, y se borra manualmente en [src/ingestion/parser.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/ingestion/parser.py:83).

Impacto:

- Si falla el LLM, quedan temporales.
- Dos ingestas concurrentes pueden pisarse.
- `data/` mezcla corpus, outputs y archivos temporales.

Mejora:

- Usar `tempfile.TemporaryDirectory`.
- Pasar rutas como `Path`, no construir strings globales.
- Hacer cleanup con context managers.
- Guardar artefactos de parsing de forma versionada: raw PDF, extracted markdown, page images opcionales, metadata.

Ademas, `_clean_markdown` elimina todos los `#` de cualquier encabezado en [src/ingestion/parser.py](/Users/albertovacas/Desktop/ai_projects/docuagent/src/ingestion/parser.py:26). Eso contradice el objetivo de preservar estructura y reduce la calidad del splitter por headers.

## Arquitectura objetivo

### Capas propuestas

```text
docuagent/
  src/docuagent/
    domain/
      documents.py
      chunks.py
      answers.py
    application/
      ingest_document.py
      answer_question.py
      evaluate_rag.py
    infrastructure/
      llms/
      vectorstores/
      observability/
      parsers/
    interfaces/
      cli.py
      api.py
      jobs.py
    prompts/
    settings.py
```

Regla de dependencia:

- `domain` no importa LangChain, Qdrant, Langfuse ni providers.
- `application` orquesta casos de uso.
- `infrastructure` adapta proveedores.
- `interfaces` expone CLI/API/jobs.

### Contratos minimos

`DocumentParser`:

- Input: `DocumentSource`
- Output: `ParsedDocument`
- Incluye paginas, texto, tablas, warnings, coste estimado y metodo usado.

`Chunker`:

- Input: `ParsedDocument`
- Output: lista de `DocumentChunk`
- Determinista, testeable sin red.

`VectorRepository`:

- `upsert_chunks(chunks)`
- `search(query, filters, limit)`
- `delete_document(document_id)`

`RAGService`:

- `answer(question, filters) -> Answer`
- `Answer` incluye texto, citas, chunks usados, scores y metadata de trazabilidad.

## Mapa por dimensiones

### Arquitectura

Estado actual: acoplamiento directo entre agente, vector store, settings, prompts y proveedores.

Acciones:

- Crear paquetes de dominio y aplicacion.
- Convertir `RetrievalAgent` en servicio orquestador con dependencias inyectadas.
- Separar ingestion pipeline de query pipeline.
- Introducir interfaces/protocolos para LLM, embeddings, vector store y reranker.

### Mantenibilidad

Estado actual: codigo compacto pero con estado oculto, prints, imports no usados y mezcla de responsabilidades.

Acciones:

- Eliminar imports no usados (`os` en agente y vector store).
- Sustituir `print` por logging estructurado.
- Tipar inputs/outputs principales.
- Cambiar estado mutable `self.documents` por retornos explicitos.
- Mover notebooks a `experiments/` o documentar cuales son canónicos.

### Escalabilidad

Estado actual: ingesta secuencial por pagina y embeddings uno a uno.

Acciones:

- Batch embeddings en grupos configurables.
- Procesamiento concurrente de paginas con limite de concurrencia.
- Cola/job para ingestas largas.
- Separar servicio online de workers offline.
- Controlar backpressure contra LLMs y Qdrant.

### Rendimiento

Estado actual: inicializar `TextEmbedding`, Qdrant y ranker en constructores puede ser costoso; reranking siempre procesa todo lo recuperado.

Acciones:

- Reusar clientes por lifecycle de app.
- Batch embedding y batch upsert.
- Cachear parser/OCR por hash de pagina.
- Limitar reranking por `k` y token budget.
- Medir latencias por etapa: parse, embed, search, rerank, generate.

### Observabilidad

Estado actual: Langfuse existe, pero mezclado con callbacks globales y `print`.

Acciones:

- Definir trace ids por documento/pregunta.
- Registrar inputs/outputs sanitizados por etapa.
- Capturar retrieval metrics: `k`, scores, documentos, paginas, top_n, token budget.
- Enviar errores con contexto operativo.
- Crear dashboards de latencia, coste, calidad y tasa de "no answer".

### Seguridad

Estado actual: `.env` no esta en `.gitignore`; secretos obligatorios se cargan al importar.

Acciones:

- Agregar `.env`, `.env.*`, credenciales y outputs sensibles a `.gitignore`.
- Crear `.env.example` sin secretos.
- Sanitizar prompts/traces antes de Langfuse si contienen documentos privados.
- Separar corpus de ejemplo de corpus privado.
- Validar archivos de entrada: tipo, tamano, paginas, limites de OCR.

### Developer experience

Estado actual: sin README operativo, test roto y entrypoint vacio.

Acciones:

- README con setup, variables, comandos y arquitectura.
- `Makefile` o scripts `uv run docuagent ...`.
- CLI minima: `ingest`, `ask`, `eval`.
- Configurar `ruff`, `mypy` opcional y `pytest`.
- CI que ejecute tests unitarios sin secretos.

### Testing

Estado actual: solo una prueba manual que llama API externa y falla en collection.

Acciones:

- Unit tests para `_is_complex`, cleaning, chunking y context builder.
- Tests con fakes para LLM, vector store y reranker.
- Contract tests para payload Qdrant sin tocar cloud.
- Golden tests de parser con PDFs pequenos.
- Evaluaciones RAG con dataset de preguntas/respuestas esperadas.

### Diseno de agentes y LLMs

Estado actual: `RetrievalAgent` es mas un servicio RAG que un agente; no hay planificacion, herramientas ni memoria conversacional.

Acciones:

- Nombrarlo `RAGAnswerService` si no necesita autonomia agentica.
- Si se desea agente real, definir herramientas explicitas: search, cite, inspect_page, summarize_table.
- Implementar query rewriting opcional antes de retrieval.
- Implementar answer validation con juez LLM o reglas de citas.
- Forzar salida estructurada con citas y abstencion.

### Calidad RAG

Estado actual: no hay evaluacion de precision, recall, faithfulness ni citation accuracy.

Acciones:

- Crear eval set con preguntas factuales del PDF DeepSeek.
- Medir retrieval recall@k y rerank MRR/NDCG.
- Medir faithfulness y citation correctness.
- Guardar cada experimento con version de prompt, modelo, embedding y chunking.
- Introducir filtros por documento y pagina.

### Despliegue

Estado actual: no hay Dockerfile, API ni worker.

Acciones:

- Definir API FastAPI para query.
- Worker separado para ingestion.
- Dockerfile multi-stage.
- Healthchecks: config, Qdrant, LLM provider, Langfuse opcional.
- Variables por entorno: local, staging, prod.

### Coste operativo

Estado actual: OCR multimodal puede disparar coste por pagina compleja; no hay presupuestos ni cache.

Acciones:

- Estimar coste por documento antes de ingestar.
- Cache por hash de pagina y documento.
- Limites de paginas, concurrencia y tokens.
- Fallback de OCR local o texto puro.
- Dashboard de coste por documento, usuario y proveedor.

### Claridad del dominio

Estado actual: "memory", "documents", "passages", "chunks" y "context" se mezclan.

Acciones:

- Definir lenguaje ubicuo:
  - `Document`: archivo fuente.
  - `Page`: unidad fisica del documento.
  - `Chunk`: unidad indexada.
  - `Evidence`: chunk seleccionado para responder.
  - `Answer`: respuesta con citas y confianza.
- Reflejar esos terminos en tipos, nombres y payloads.

## Roadmap priorizado

### Fase 0 - Estabilizacion inmediata

Objetivo: que el prototipo responda de forma fiable y sea ejecutable por otra persona.

- Arreglar `context_text[:top_n]`.
- Arreglar imports de tests.
- Anadir `.env` a `.gitignore` y crear `.env.example`.
- README minimo con setup y comandos.
- CLI minima para `ingest` y `ask`.
- Tests unitarios sin red para chunking, parser heuristico y context builder.

Exito medible:

- `uv run pytest` pasa sin secretos.
- Una pregunta contra el documento de ejemplo devuelve citas con paginas correctas.

### Fase 1 - Arquitectura limpia

Objetivo: separar dominio de infraestructura.

- Mover codigo a paquete `src/docuagent`.
- Introducir tipos `DocumentChunk`, `SearchResult`, `Answer`.
- Crear interfaces para parser, embeddings, vector store, reranker y LLM.
- Eliminar estado mutable de `VectorStore.upload_documents`.
- IDs deterministas para chunks.

Exito medible:

- Se puede testear el pipeline RAG completo con fakes.
- Reingestar un documento no duplica chunks.

### Fase 2 - Calidad RAG y evaluacion

Objetivo: mejorar precision de respuestas con datos, no intuicion.

- Crear dataset de evaluacion.
- Medir retrieval recall@k, citation accuracy y faithfulness.
- Versionar prompts y parametros.
- Anadir query rewriting y respuesta estructurada.
- Comparar modelos/embeddings/rerankers con coste y latencia.

Exito medible:

- Cada cambio en prompt/chunking/modelo produce reporte de calidad.
- Hay umbrales minimos antes de desplegar.

### Fase 3 - Operacion y despliegue

Objetivo: convertirlo en servicio operable.

- FastAPI para consultas.
- Worker de ingesta.
- Dockerfile y docker-compose local con Qdrant opcional.
- Healthchecks y logging estructurado.
- Config por entorno.
- CI basica.

Exito medible:

- Nuevo entorno arranca con un comando.
- Fallos de provider o vector store son visibles y degradan de forma controlada.

### Fase 4 - Escalado y coste

Objetivo: soportar volumen con coste predecible.

- Batch/concurrency control.
- Cache de OCR y embeddings.
- Rate limiting.
- Quotas por usuario/documento.
- Dashboards de coste y latencia.
- Estrategia de retencion y borrado por documento.

Exito medible:

- Coste por documento estimado antes de ingestar.
- Latencia p95 por pregunta bajo objetivo definido.

## Backlog recomendado

### Alto impacto, bajo esfuerzo

- Corregir slicing de contexto.
- Cambiar `Pagina` a `page` en todo el pipeline.
- Agregar `.env` a `.gitignore`.
- Reparar test import.
- Crear `README.md`.
- Sustituir `print` por `logging`.

### Alto impacto, esfuerzo medio

- Refactorizar `VectorStore` para input explicito e IDs deterministas.
- Crear CLI real.
- Crear tipos de dominio.
- Tests unitarios con fakes.
- Respuesta estructurada con citas.

### Alto impacto, esfuerzo alto

- API + worker.
- Evaluacion RAG automatizada.
- Observabilidad completa por pipeline.
- Cache y control de coste.
- Multi-document retrieval con filtros.

## Decision arquitectonica recomendada

Mi recomendacion principal: no construir todavia una "plataforma de agentes" generica. Primero convertir DocuAgent en un RAG documental robusto, evaluable y operable. El patron de agente deberia aparecer solo si hay herramientas y decisiones reales que tomar: inspeccionar paginas, comparar documentos, pedir aclaraciones, ejecutar retrieval iterativo o validar tablas.

La forma objetivo seria:

```text
PDF -> Parser -> ParsedDocument -> Chunker -> VectorRepository
                                            |
Question -> QueryPipeline -> Retriever -> Reranker -> AnswerGenerator -> Answer + Evidence
```

Con esto se gana claridad, testabilidad y control de coste sin perder capacidad de evolucionar hacia agentes mas avanzados.

## Verificacion realizada

Comandos ejecutados:

- `uv run pytest -q`
- `uv run python -c "from src.agents.retrieval_agent import RetrievalAgent; print('import ok')"`

Resultado:

- Importar `RetrievalAgent` funciona.
- La suite de tests falla en collection por `ModuleNotFoundError: No module named 'docuagent'`, causado por el import de [tests/test_gcp.py](/Users/albertovacas/Desktop/ai_projects/docuagent/tests/test_gcp.py:1).

