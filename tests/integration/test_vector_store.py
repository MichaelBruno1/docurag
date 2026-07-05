import pytest
from src.domain.entities import Chunk, QueryResult
from src.infrastructure.adapters.vector_store import QdrantVectorStore

def test_vector_store_operations():
    # Run Qdrant in-memory for fast, side-effect free integration testing
    store = QdrantVectorStore(path=":memory:")
    
    # 1. Create test chunks
    chunk1 = Chunk(
        chunk_id="chunk-1",
        document_id="doc-A",
        content="O motor a combustão interna foi inventado no século XIX.",
        tokens_count=10,
        secao="Introdução",
        pagina=1,
        palavras_chave=["motor", "combustão"],
        embedding_version="fake-model"
    )
    setattr(chunk1, "version_timestamp", "v1")
    
    chunk2 = Chunk(
        chunk_id="chunk-2",
        document_id="doc-A",
        content="Manual de manutenção preventiva: troque o óleo a cada 10.000 km.",
        tokens_count=12,
        secao="Manutenção",
        pagina=2,
        palavras_chave=["óleo", "manutenção"],
        embedding_version="fake-model"
    )
    setattr(chunk2, "version_timestamp", "v1")
    
    chunk3 = Chunk(
        chunk_id="chunk-3",
        document_id="doc-B",
        content="Política de privacidade de dados: as diretrizes de LGPD são seguidas.",
        tokens_count=12,
        secao="Privacidade",
        pagina=1,
        palavras_chave=["LGPD", "privacidade"],
        embedding_version="fake-model"
    )
    setattr(chunk3, "version_timestamp", "v1")
    
    # Vector size: 3 (Fake embeddings matching FakeEmbeddingProvider)
    embeddings = [
        [0.9, 0.1, 0.1],  # motor
        [0.1, 0.9, 0.1],  # manutenção
        [0.1, 0.1, 0.9]   # LGPD
    ]
    
    # 2. Test upsert
    store.upsert_chunks([chunk1, chunk2, chunk3], embeddings)
    
    stats = store.get_stats()
    assert stats["total_chunks"] == 3
    assert stats["collection_status"] == "active"
    
    # 3. Test search similarity (no filters)
    # Search for "motor" (vector is close to [1.0, 0.0, 0.0])
    results = store.search_similarity(query_embedding=[1.0, 0.0, 0.0], filter_metadata={}, top_k=2)
    assert len(results) == 2
    assert results[0].chunk.chunk_id == "chunk-1"
    assert "motor" in results[0].chunk.content
    
    # 4. Test search with metadata filters
    # Search with filter: limit to doc-B
    results_filter = store.search_similarity(
        query_embedding=[0.0, 0.0, 1.0],
        filter_metadata={"document_id": "doc-B"},
        top_k=2
    )
    assert len(results_filter) == 1
    assert results_filter[0].chunk.chunk_id == "chunk-3"
    assert results_filter[0].chunk.document_id == "doc-B"
    
    # 4.5. Test get_all_chunks (scroll method)
    all_chunks_doc_a = store.get_all_chunks({"document_id": "doc-A"})
    assert len(all_chunks_doc_a) == 2
    assert {c.chunk_id for c in all_chunks_doc_a} == {"chunk-1", "chunk-2"}
    
    # 5. Test versioned delete (conditional delete)
    # Upsert a new version of chunk-1 but with different content
    chunk1_v2 = Chunk(
        chunk_id="chunk-1-v2", # Different content produces different chunk_id
        document_id="doc-A",
        content="O motor a combustão interna foi inventado no século XIX por engenheiros alemães.",
        tokens_count=13,
        secao="Introdução",
        pagina=1,
        palavras_chave=["motor", "combustão", "alemães"],
        embedding_version="fake-model"
    )
    setattr(chunk1_v2, "version_timestamp", "v2")
    
    # Let's say chunk-2 was removed in version 2
    
    # Upsert version 2 of doc-A
    store.upsert_chunks([chunk1_v2], [[0.9, 0.15, 0.05]])
    
    # Delete old chunks of doc-A (excluding version "v2")
    # This should remove chunk-1 (v1) and chunk-2 (v1), keeping only chunk1_v2 (v2)
    store.delete_document_chunks(document_id="doc-A", exclude_version="v2")
    
    # Total chunks in DB should be: chunk1_v2 (v2) and chunk-3 (doc-B, v1) -> Total 2 chunks
    stats_after = store.get_stats()
    assert stats_after["total_chunks"] == 2
    
    # Search for doc-A chunks
    results_doc_a = store.search_similarity(
        query_embedding=[1.0, 0.0, 0.0],
        filter_metadata={"document_id": "doc-A"},
        top_k=5
    )
    assert len(results_doc_a) == 1
    assert results_doc_a[0].chunk.chunk_id == "chunk-1-v2"
    
    # 6. Test complete delete of doc-B
    store.delete_document_chunks(document_id="doc-B")
    
    stats_final = store.get_stats()
    assert stats_final["total_chunks"] == 1 # Only chunk1_v2 left
