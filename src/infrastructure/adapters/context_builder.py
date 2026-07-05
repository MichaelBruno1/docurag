import logging
from typing import List

from src.domain.entities import QueryResult, RetrievalContext
from src.domain.ports import ContextBuilder
from src.infrastructure.adapters.chunker import count_tokens
from src.infrastructure.adapters.retriever import jaccard_similarity

logger = logging.getLogger(__name__)

class SimpleContextBuilder(ContextBuilder):
    def __init__(self, max_context_tokens: int = 5000):
        # We target a 4.5k to 5k token budget for chunks to leave plenty of room
        # for system prompt, user query, and generated response under the 8k total token ceiling.
        self.max_context_tokens = max_context_tokens

    def build_context(self, query: str, results: List[QueryResult]) -> RetrievalContext:
        logger.info(f"Montando contexto. Budget máximo de tokens: {self.max_context_tokens}")
        
        used_chunks: List[QueryResult] = []
        discarded_chunks: List[QueryResult] = []
        
        current_tokens = 0
        context_parts = []
        
        # Deduplication threshold for final context inclusion (Jaccard > 0.7 is redundant)
        dedup_threshold = 0.7
        
        # Chunks are already sorted descending by re-ranker score (highest relevance first)
        for res in results:
            chunk = res.chunk
            
            # Double check redundancy against already selected chunks
            is_redundant = False
            for used in used_chunks:
                if jaccard_similarity(chunk.content, used.chunk.content) > dedup_threshold:
                    is_redundant = True
                    break
                    
            if is_redundant:
                logger.debug(f"Chunk {chunk.chunk_id} descartado do contexto por redundância.")
                discarded_chunks.append(res)
                continue
                
            # Format block with human-readable citation tag for Qwen-9B
            page_info = f" (Página {chunk.pagina})" if chunk.pagina else ""
            source_tag = f"[Fonte: Seção '{chunk.secao or 'Geral'}' no arquivo '{chunk.nome_arquivo or chunk.document_id}'{page_info}]"
            chunk_text = f"{source_tag}\n{chunk.content}\n---\n"
            
            chunk_tokens = count_tokens(chunk_text)
            
            if current_tokens + chunk_tokens <= self.max_context_tokens:
                current_tokens += chunk_tokens
                context_parts.append(chunk_text)
                used_chunks.append(res)
            else:
                logger.debug(f"Chunk {chunk.chunk_id} descartado: estourou o budget de tokens ({current_tokens + chunk_tokens} > {self.max_context_tokens}).")
                discarded_chunks.append(res)
                
        # Join final context parts
        context_text = "\n".join(context_parts)
        logger.info(f"Contexto montado. Usou {len(used_chunks)} chunks, descartou {len(discarded_chunks)}. Total de tokens: {current_tokens}")
        
        return RetrievalContext(
            context_text=context_text,
            used_chunks=used_chunks,
            discarded_chunks=discarded_chunks
        )
