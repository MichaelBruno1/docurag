import logging
from typing import Any

from src.infrastructure.database.repository import SQLiteDocumentRepository
from src.infrastructure.adapters.parsers import ParserRegistry
from src.infrastructure.adapters.normalizer import RegexTextNormalizer
from src.infrastructure.adapters.enricher import YakeEnricher
from src.infrastructure.adapters.chunker import HybridChunker
from src.infrastructure.adapters.embeddings import SentenceTransformersEmbeddingProvider
from src.infrastructure.adapters.vector_store import QdrantVectorStore
from src.application.use_cases import IngestDocumentUseCase

logger = logging.getLogger("docurag_tasks")

# Initialize shared components once at module loading time (Worker Singleton Pattern)
logger.info("Inicializando componentes do pipeline no Worker...")
repo = SQLiteDocumentRepository()

parser_registry = ParserRegistry()

normalizer = RegexTextNormalizer()
enricher = YakeEnricher()
embedding_provider = SentenceTransformersEmbeddingProvider()
vector_store = QdrantVectorStore()

# HybridChunker initialized with singleton embedding provider
chunker = HybridChunker(embedding_provider=embedding_provider)

ingest_use_case = IngestDocumentUseCase(
    parser_registry=parser_registry,
    normalizer=normalizer,
    enricher=enricher,
    chunker=chunker,
    embedding_provider=embedding_provider,
    vector_store=vector_store,
    document_repository=repo
)

def process_document_task(file_path: str, filename: str, document_id: str) -> None:
    logger.info(f"Tarefa process_document_task iniciada para o documento: {filename} (ID: {document_id})")
    
    # 1. Update status to 'processando'
    try:
        doc = repo.get_document(document_id)
        if doc:
            doc.status = "processando"
            repo.save_document(doc)
    except Exception as e:
        logger.error(f"Erro ao atualizar status inicial para o documento {document_id}: {e}")

    # 2. Run use case execution
    try:
        ingest_use_case.execute(file_path, filename, document_id)
        logger.info(f"Tarefa process_document_task concluída com sucesso para o documento {document_id}.")
    except Exception as e:
        logger.exception(f"Falha ao executar ingestão para o documento {document_id}: {e}")
        # Update SQLite entry status to 'erro'
        try:
            doc = repo.get_document(document_id)
            if doc:
                doc.status = "erro"
                doc.error_message = str(e)
                repo.save_document(doc)
        except Exception as db_err:
            logger.error(f"Erro ao salvar status de erro no banco de dados para {document_id}: {db_err}")
        raise e
