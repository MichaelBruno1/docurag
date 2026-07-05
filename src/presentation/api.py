import os
import json
import uuid
import logging
import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Security, File, UploadFile, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from redis import Redis
from rq import Queue

from src.config import settings
from src.domain.entities import Document
from src.infrastructure.database.repository import SQLiteDocumentRepository
from src.infrastructure.adapters.vector_store import QdrantVectorStore
from src.infrastructure.adapters.embeddings import SentenceTransformersEmbeddingProvider
from src.infrastructure.adapters.retriever import HybridRetriever
from src.infrastructure.adapters.reranker import CrossEncoderReranker
from src.infrastructure.adapters.context_builder import SimpleContextBuilder
from src.infrastructure.adapters.llm_provider import LMStudioLLMProvider
from src.application.use_cases import QueryUseCase, RemoveDocumentUseCase
from src.infrastructure.adapters.benchmark_runner import AutomatedBenchmarkRunner

logger = logging.getLogger("docurag_api")

# Pydantic schemas
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    top_k: Optional[int] = Field(default=5, ge=1, le=15)
    filters: Optional[Dict[str, Any]] = None

class QueryResponse(BaseModel):
    trace_id: str
    query: str
    response: str
    context_text: str
    used_chunks: List[Dict[str, Any]]
    discarded_chunks: List[Dict[str, Any]]

class IngestResponse(BaseModel):
    document_id: str
    nome_arquivo: str
    status: str

# Shared singletons (initialized during lifespan)
db_repo: Optional[SQLiteDocumentRepository] = None
vector_store: Optional[QdrantVectorStore] = None
embedding_provider: Optional[SentenceTransformersEmbeddingProvider] = None
retriever: Optional[HybridRetriever] = None
reranker: Optional[CrossEncoderReranker] = None
context_builder: Optional[SimpleContextBuilder] = None
llm_provider: Optional[LMStudioLLMProvider] = None
query_use_case: Optional[QueryUseCase] = None
remove_use_case: Optional[RemoveDocumentUseCase] = None
benchmark_runner: Optional[AutomatedBenchmarkRunner] = None
redis_conn: Optional[Redis] = None
task_queue: Optional[Queue] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_repo, vector_store, embedding_provider, retriever, reranker
    global context_builder, llm_provider, query_use_case, remove_use_case, benchmark_runner, redis_conn, task_queue
    
    logger.info("=== Inicializando dependências da API do DocuRAG ===")
    
    # 1. Initialize SQLite Database Repo
    db_repo = SQLiteDocumentRepository()
    
    # 2. Initialize Qdrant local Vector Store
    vector_store = QdrantVectorStore()
    
    # 3. Load SentenceTransformers Embedding Provider (loads weights into VRAM once)
    embedding_provider = SentenceTransformersEmbeddingProvider()
    
    # 4. Load CrossEncoder Reranker (loads weights into VRAM once)
    reranker = CrossEncoderReranker()
    
    # 5. Initialize Hybrid Retriever (configures toggleable hybrid BM25 + RRF)
    # We read config from settings or environment.
    retriever = HybridRetriever(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        use_hybrid=True  # default is hybrid, can be configured
    )
    
    # 6. Initialize Context Builder and LLM Provider
    context_builder = SimpleContextBuilder()
    llm_provider = LMStudioLLMProvider()
    
    # 7. Initialize Use Cases
    query_use_case = QueryUseCase(
        embedding_provider=embedding_provider,
        retriever=retriever,
        reranker=reranker,
        context_builder=context_builder,
        llm_provider=llm_provider
    )
    remove_use_case = RemoveDocumentUseCase(vector_store=vector_store)
    
    # 7.5. Initialize Benchmark Runner
    benchmark_runner = AutomatedBenchmarkRunner(
        retriever=retriever,
        reranker=reranker,
        context_builder=context_builder,
        llm_provider=llm_provider,
        vector_store=vector_store
    )
    
    # 8. Initialize Redis & RQ queue
    try:
        redis_conn = Redis.from_url(settings.REDIS_URL)
        redis_conn.ping()
        task_queue = Queue("docurag_tasks", connection=redis_conn)
        logger.info("Fila Redis RQ conectada com sucesso na API.")
    except Exception as e:
        logger.error(f"Falha ao conectar com o Redis no startup da API: {e}. Ingestão assíncrona falhará.")
        
    logger.info("=== Dependências carregadas com sucesso. API pronta. ===")
    yield
    logger.info("=== Encerrando API do DocuRAG ===")

app = FastAPI(
    title="DocuRAG Platform API",
    description="Plataforma de IA Generativa RAG Corporativa para Ingestão e Consulta Semântica Grounded de Documentos.",
    version="1.1.0",
    lifespan=lifespan
)

# Servir arquivos estáticos do Dashboard
app.mount("/dashboard", StaticFiles(directory="src/presentation/static", html=True), name="static")

@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/dashboard")

# API Key Security Header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_key(header_value: Optional[str] = Security(api_key_header)) -> str:
    if not header_value or header_value != settings.API_KEY:
        logger.warning("Tentativa de acesso não autorizada com chave de API ausente ou inválida.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não autorizado: Chave de API inválida."
        )
    return header_value

# Helper dependency to verify lifespan singletons are ready
def get_query_use_case() -> QueryUseCase:
    if query_use_case is None:
        raise HTTPException(status_code=503, detail="Serviço indisponível: Modelos de IA não inicializados.")
    return query_use_case

# Endpoints

@app.post("/documents/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(
    file: UploadFile = File(...),
    api_key: str = Depends(get_api_key)
):
    # Verify file extension
    filename = file.filename or "uploaded_file"
    ext = f".{filename.split('.')[-1].lower()}"
    allowed_extensions = {".pdf", ".docx", ".xlsx", ".txt"}
    
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de arquivo '{ext}' não suportado. Use PDF, DOCX, XLSX ou TXT."
        )
        
    # Generate unique UUID for the document
    document_id = str(uuid.uuid4())
    
    # Save uploaded file temporarily to data/uploads
    # Collision-proof filename matching document_id
    saved_filename = f"{document_id}{ext}"
    local_path = os.path.join(settings.UPLOAD_DIR, saved_filename)
    
    try:
        file_size = 0
        with open(local_path, "wb") as buffer:
            while chunk := await file.read(65536):
                buffer.write(chunk)
                file_size += len(chunk)
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo em disco: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao gravar arquivo de upload.")
        
    # Register document in SQLite database
    try:
        new_doc = Document(
            document_id=document_id,
            nome_arquivo=filename,
            formato=ext.upper().replace(".", ""),
            tamanho_bytes=file_size,
            created_at=datetime.datetime.utcnow(),
            status="enfileirado"
        )
        db_repo.save_document(new_doc)
    except Exception as e:
        logger.error(f"Erro ao registrar documento no banco de dados: {e}")
        # Clean up local file
        if os.path.exists(local_path):
            os.remove(local_path)
        raise HTTPException(status_code=500, detail="Erro interno ao criar registro de metadados no SQLite.")
        
    # Enqueue task in Redis Queue
    if task_queue is None:
        # Fallback if Redis was offline at startup: retry connect
        try:
            r = Redis.from_url(settings.REDIS_URL)
            q = Queue("docurag_tasks", connection=r)
            q.enqueue("src.infrastructure.queue.tasks.process_document_task", local_path, filename, document_id)
        except Exception as queue_err:
            logger.critical(f"Redis indisponível para enfileiramento: {queue_err}")
            new_doc.status = "erro"
            new_doc.error_message = f"Falha ao enfileirar no Redis: {queue_err}"
            db_repo.save_document(new_doc)
            raise HTTPException(status_code=500, detail="Redis offline. Falha ao enfileirar tarefa de processamento.")
    else:
        try:
            task_queue.enqueue(
                "src.infrastructure.queue.tasks.process_document_task",
                local_path,
                filename,
                document_id
            )
        except Exception as e:
            logger.error(f"Erro ao enfileirar tarefa no RQ: {e}")
            new_doc.status = "erro"
            new_doc.error_message = f"Falha ao enfileirar no RQ: {e}"
            db_repo.save_document(new_doc)
            raise HTTPException(status_code=500, detail="Erro ao enviar tarefa para fila de processamento assíncrono.")
            
    return IngestResponse(
        document_id=document_id,
        nome_arquivo=filename,
        status="enfileirado"
    )

@app.get("/documents/{document_id}")
async def get_document_status(
    document_id: str,
    api_key: str = Depends(get_api_key)
):
    doc = db_repo.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Documento com ID {document_id} não encontrado.")
    return doc

@app.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    api_key: str = Depends(get_api_key)
):
    doc = db_repo.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Documento com ID {document_id} não encontrado.")
        
    # 1. Remove vector chunks from Qdrant
    try:
        vector_store.delete_document_chunks(document_id)
    except Exception as e:
        logger.error(f"Erro ao remover chunks do Qdrant para {document_id}: {e}")
        # Continue deletion flow even if Qdrant throws, to prevent hanging references
        
    # 2. Delete local uploaded file
    ext = f".{doc.nome_arquivo.split('.')[-1].lower()}"
    local_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}{ext}")
    if os.path.exists(local_path):
        try:
            os.remove(local_path)
        except Exception as e:
            logger.error(f"Erro ao deletar arquivo local {local_path}: {e}")
            
    # 3. Remove metadata from SQLite
    try:
        db_repo.delete_document(document_id)
    except Exception as e:
        logger.error(f"Erro ao deletar registro SQLite para {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao remover metadados do SQLite.")
        
    return {"detail": "Documento removido com sucesso de todas as camadas de armazenamento."}

@app.post("/query", response_model=QueryResponse)
async def query_rag(
    req: QueryRequest,
    api_key: str = Depends(get_api_key),
    use_case: QueryUseCase = Depends(get_query_use_case)
):
    try:
        filter_metadata = req.filters or {}
        # Execute use case
        result = use_case.execute(
            query=req.query,
            filter_metadata=filter_metadata,
            top_k=req.top_k or 5
        )
        return result
    except Exception as e:
        logger.exception(f"Erro ao processar consulta: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno no pipeline de RAG: {str(e)}")

@app.get("/stats")
async def get_system_stats(
    api_key: str = Depends(get_api_key)
):
    try:
        db_stats = db_repo.get_stats()
        qdrant_stats = vector_store.get_stats()
        docs = db_repo.list_documents()
        
        return {
            "database_stats": db_stats,
            "vector_store_stats": qdrant_stats,
            "documents": [
                {
                    "document_id": d.document_id,
                    "nome_arquivo": d.nome_arquivo,
                    "status": d.status,
                    "created_at": d.created_at.isoformat(),
                    "categoria": d.categoria,
                    "error_message": d.error_message
                }
                for d in docs
            ]
        }
    except Exception as e:
        logger.error(f"Erro ao consultar estatísticas do sistema: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao recuperar métricas estatísticas.")

@app.post("/benchmark/run")
async def run_benchmark_endpoint(
    config_label: str = "Padrão",
    num_questions: int = 30,
    api_key: str = Depends(get_api_key)
):
    if benchmark_runner is None:
        raise HTTPException(status_code=503, detail="Serviço de benchmark indisponível no momento.")
    try:
        result = benchmark_runner.run_benchmark(config_label=config_label, num_questions=num_questions)
        return {
            "message": f"Benchmark para '{config_label}' executado com sucesso.",
            "timestamp": result["timestamp"],
            "average_metrics": result["average_metrics"]
        }
    except Exception as e:
        logger.exception(f"Erro ao executar benchmark: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao rodar benchmark: {str(e)}")

@app.get("/benchmark/results")
async def get_benchmark_results(
    api_key: str = Depends(get_api_key)
):
    if benchmark_runner is None:
        raise HTTPException(status_code=503, detail="Serviço de benchmark indisponível.")
    history_path = benchmark_runner.history_path
    if not os.path.exists(history_path):
        return []
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
        return history
    except Exception as e:
        logger.error(f"Erro ao ler histórico de benchmark: {e}")
        raise HTTPException(status_code=500, detail="Erro ao ler histórico de benchmark.")

@app.get("/health")
async def health_check():
    # Simple check for database connection
    db_ok = False
    try:
        if db_repo is not None:
            db_repo.get_stats()
            db_ok = True
    except Exception:
        pass
        
    # Check Qdrant connection
    qdrant_ok = False
    try:
        if vector_store is not None:
            vector_store.get_stats()
            qdrant_ok = True
    except Exception:
        pass
        
    # Check Redis connection
    redis_ok = False
    try:
        if redis_conn is not None:
            redis_conn.ping()
            redis_ok = True
    except Exception:
        pass
        
    status_code = 200 if (db_ok and qdrant_ok) else 503
    return {
        "status": "healthy" if status_code == 200 else "unhealthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "services": {
            "sqlite": "online" if db_ok else "offline",
            "qdrant": "online" if qdrant_ok else "offline",
            "redis": "online" if redis_ok else "offline"
        }
    }
