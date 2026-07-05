import logging
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi

from src.domain.entities import Chunk, QueryResult
from src.domain.ports import Retriever, EmbeddingProvider, VectorStore

logger = logging.getLogger(__name__)

def jaccard_similarity(text1: str, text2: str) -> float:
    """Calculates text overlap using Jaccard Similarity of words."""
    w1 = set(text1.lower().split())
    w2 = set(text2.lower().split())
    if not w1 or not w2:
        return 0.0
    return len(w1.intersection(w2)) / len(w1.union(w2))


class HybridRetriever(Retriever):
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        use_hybrid: bool = False,
        rrf_constant: int = 60
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.use_hybrid = use_hybrid
        self.rrf_constant = rrf_constant

    def retrieve(self, query: str, filter_metadata: Dict[str, Any], top_k: int) -> List[QueryResult]:
        logger.info(f"Iniciando recuperação de chunks. Query: '{query}' | Híbrida: {self.use_hybrid} | K: {top_k}")
        
        # 1. Vector Search (always performed)
        query_emb = self.embedding_provider.get_embedding(query)
        # In hybrid mode we fetch more candidates for fusion, in pure mode we fetch top_k + buffer for deduplication
        vector_limit = 50 if self.use_hybrid else top_k * 2
        vector_results = self.vector_store.search_similarity(query_emb, filter_metadata, top_k=vector_limit)
        
        if not self.use_hybrid:
            # Apply deduplication on vector results
            deduplicated = self._deduplicate(vector_results, top_k)
            return deduplicated
            
        # 2. Lexical Search (BM25) over filtered chunks
        all_filtered_chunks = self.vector_store.get_all_chunks(filter_metadata)
        if len(all_filtered_chunks) == 0:
            logger.warning("Nenhum chunk filtrado disponível para busca lexical. Usando apenas busca vetorial.")
            return self._deduplicate(vector_results, top_k)
            
        # Build BM25 index on-the-fly for the filtered partition
        tokenized_corpus = [c.content.lower().split() for c in all_filtered_chunks]
        bm25 = BM25Okapi(tokenized_corpus)
        
        tokenized_query = query.lower().split()
        bm25_scores = bm25.get_scores(tokenized_query)
        
        # Sort chunks by BM25 score
        lexical_results = []
        for chunk, score in zip(all_filtered_chunks, bm25_scores):
            if score > 0.0:  # Only consider text-matching chunks
                lexical_results.append(QueryResult(chunk=chunk, score=float(score)))
        # Sort descending by lexical score
        lexical_results.sort(key=lambda x: x.score, reverse=True)
        # Limit to top 50 for fusion
        lexical_results = lexical_results[:50]
        
        # 3. Reciprocal Rank Fusion (RRF)
        fused_results = self._reciprocal_rank_fusion(vector_results, lexical_results, top_k * 2)
        
        # 4. Deduplicate final fused results
        return self._deduplicate(fused_results, top_k)

    def _reciprocal_rank_fusion(
        self,
        vector_list: List[QueryResult],
        lexical_list: List[QueryResult],
        limit: int
    ) -> List[QueryResult]:
        # RRF maps chunk_id to fused score
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}
        
        # Process vector ranks
        for rank, res in enumerate(vector_list):
            chunk_id = res.chunk.chunk_id
            chunk_map[chunk_id] = res.chunk
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (self.rrf_constant + rank))
            
        # Process lexical ranks
        for rank, res in enumerate(lexical_list):
            chunk_id = res.chunk.chunk_id
            chunk_map[chunk_id] = res.chunk
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (self.rrf_constant + rank))
            
        # Sort by RRF score descending
        sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for cid, score in sorted_ids[:limit]:
            results.append(QueryResult(chunk=chunk_map[cid], score=score))
        return results

    def _deduplicate(self, results: List[QueryResult], top_k: int) -> List[QueryResult]:
        # Deduplication using Jaccard Similarity threshold of 0.7
        dedup_threshold = 0.7
        unique_results: List[QueryResult] = []
        
        for res in results:
            if len(unique_results) >= top_k:
                break
                
            is_redundant = False
            for unique in unique_results:
                if jaccard_similarity(res.chunk.content, unique.chunk.content) > dedup_threshold:
                    is_redundant = True
                    break
                    
            if not is_redundant:
                unique_results.append(res)
                
        return unique_results
