import datetime
import logging
import uuid
from typing import List, Dict, Any, Optional

from src.domain.entities import Document, Chunk, QueryResult, RetrievalContext
from src.domain.ports import (
    DocumentParser, TextNormalizer, Enricher, Chunker,
    EmbeddingProvider, VectorStore, Retriever, Reranker,
    ContextBuilder, LLMProvider
)
from src.infrastructure.adapters.parsers import ParserRegistry

logger = logging.getLogger(__name__)

class IngestDocumentUseCase:
    def __init__(
        self,
        parser_registry: ParserRegistry,
        normalizer: TextNormalizer,
        enricher: Enricher,
        chunker: Chunker,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        document_repository: Any
    ):
        self.parser_registry = parser_registry
        self.normalizer = normalizer
        self.enricher = enricher
        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.document_repository = document_repository

    def execute(self, file_path: str, filename: str, document_id: str) -> None:
        logger.info(f"Iniciando caso de uso de Ingestão para o documento: {filename} (ID: {document_id})")
        
        # 1. Parse based on file extension
        ext = f".{filename.split('.')[-1].lower()}"
        parser = self.parser_registry.get_parser(ext)
        doc = parser.parse(file_path, document_id)
        
        # 2. Normalize section text contents
        is_ocr = doc.raw_metadata.get("ocr_applied", False)
        for section in doc.sections:
            section.content = self.normalizer.normalize(section.content, is_ocr)
            
        # 3. Enrich document and sections
        doc = self.enricher.enrich(doc)
        
        # 4. Generate Chunks
        chunks = self.chunker.chunk(doc)
        if not chunks:
            logger.warning(f"Nenhum chunk gerado para o documento {document_id}.")
            doc_db = self.document_repository.get_document(document_id)
            if doc_db:
                doc_db.status = "concluido"
                self.document_repository.save_document(doc_db)
            return
            
        # 5. Generate embeddings in batch
        texts = [c.content for c in chunks]
        embeddings = self.embedding_provider.get_embeddings(texts)
        
        # 6. Index (using "insert first, then delete old chunks" transactionally via timestamp)
        version_timestamp = str(datetime.datetime.utcnow().timestamp())
        for chunk in chunks:
            # Set dynamic version timestamp to chunk to distinguish it in VectorStore
            setattr(chunk, "version_timestamp", version_timestamp)
            
        # Index new chunks
        self.vector_store.upsert_chunks(chunks, embeddings)
        
        # Clean up old chunks with different version timestamp
        # In this step we delete chunks of document_id where version_timestamp != our new timestamp
        self.vector_store.delete_document_chunks(document_id, exclude_version=version_timestamp)
        
        # 7. Update status to concluido in Repository with enriched metadata
        doc_db = self.document_repository.get_document(document_id)
        if doc_db:
            doc_db.status = "concluido"
            doc_db.categoria = doc.raw_metadata.get("categoria")
            doc_db.autor = doc.raw_metadata.get("autor")
            doc_db.data_original = doc.raw_metadata.get("data_original")
            self.document_repository.save_document(doc_db)
            
        logger.info(f"Ingestão e indexação do documento {document_id} concluídas com sucesso.")


class RemoveDocumentUseCase:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    def execute(self, document_id: str) -> None:
        logger.info(f"Removendo documento {document_id} do índice.")
        self.vector_store.delete_document_chunks(document_id)
        logger.info(f"Documento {document_id} removido com sucesso.")


class QueryUseCase:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        retriever: Retriever,
        reranker: Reranker,
        context_builder: ContextBuilder,
        llm_provider: LLMProvider
    ):
        self.embedding_provider = embedding_provider
        self.retriever = retriever
        self.reranker = reranker
        self.context_builder = context_builder
        self.llm_provider = llm_provider

    def execute(self, query: str, filter_metadata: Dict[str, Any], top_k: int = 5) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        logger.info(f"Executando consulta. Query: '{query}' | Trace ID: {trace_id}")
        
        # 1. Retrieve initial candidate chunks (N > K, say N=20)
        # Filters are applied inside the retriever
        initial_results = self.retriever.retrieve(query, filter_metadata, top_k=20)
        logger.info(f"Recuperados {len(initial_results)} candidatos iniciais.")
        
        # 2. Re-rank results
        reranked_results = self.reranker.rerank(query, initial_results, top_k=top_k)
        logger.info(f"Resultados reordenados pelo Cross-Encoder. Mantidos top-{len(reranked_results)}.")
        
        # 3. Build optimized context
        context = self.context_builder.build_context(query, reranked_results)
        
        # 4. Generate response via LLM Studio
        # system prompt structure: persona, grounding, citations, honesty, language pt-BR
        system_prompt = (
            "Você é um assistente virtual corporativo encarregado de responder perguntas técnicas com base exclusivamente "
            "no contexto fornecido abaixo. Siga estas diretrizes estritamente:\n"
            "1. Responda apenas com informações contidas no contexto fornecido. Não alucine, especule ou invente dados.\n"
            "2. Cite a fonte de origem (ex: documento, seção ou página) sempre que usar uma informação do contexto.\n"
            "3. Se as informações fornecidas no contexto não forem suficientes para responder à pergunta, diga explicitamente "
            "que não encontrou essa informação nos documentos.\n"
            "4. Responda sempre em português, de forma direta e objetiva."
        )
        
        response_text = self.llm_provider.generate_response(
            system_prompt=system_prompt,
            context=context.context_text,
            user_query=query
        )
        
        # Compile audit trace output
        return {
            "trace_id": trace_id,
            "query": query,
            "response": response_text,
            "context_text": context.context_text,
            "used_chunks": [
                {
                    "chunk_id": r.chunk.chunk_id,
                    "document_id": r.chunk.document_id,
                    "secao": r.chunk.secao,
                    "pagina": r.chunk.pagina,
                    "score": r.score,
                    "content": r.chunk.content
                }
                for r in context.used_chunks
            ],
            "discarded_chunks": [
                {
                    "chunk_id": r.chunk.chunk_id,
                    "document_id": r.chunk.document_id,
                    "secao": r.chunk.secao,
                    "pagina": r.chunk.pagina,
                    "score": r.score
                }
                for r in context.discarded_chunks
            ]
        }
