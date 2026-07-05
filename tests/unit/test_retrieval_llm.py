import pytest
import httpx
from unittest.mock import MagicMock, patch

from src.domain.entities import Chunk, QueryResult
from src.infrastructure.adapters.retriever import HybridRetriever
from src.infrastructure.adapters.reranker import CrossEncoderReranker
from src.infrastructure.adapters.context_builder import SimpleContextBuilder
from src.infrastructure.adapters.llm_provider import LMStudioLLMProvider

# Fake Embedding Provider
class FakeEmbeddingProvider:
    def get_embedding(self, text: str):
        return [0.5, 0.5, 0.5]
    def get_embeddings(self, texts: list):
        return [[0.5, 0.5, 0.5] for _ in texts]
    def model_version(self) -> str:
        return "fake-model"
    def dimension(self) -> int:
        return 3

# Fake Vector Store
class FakeVectorStore:
    def __init__(self, chunks=None):
        self.chunks = chunks or []
    def search_similarity(self, query_embedding, filter_metadata, top_k):
        return [QueryResult(chunk=c, score=0.9 - idx*0.1) for idx, c in enumerate(self.chunks[:top_k])]
    def get_all_chunks(self, filter_metadata):
        return self.chunks


def test_retriever_pure_vector_and_deduplication():
    chunk1 = Chunk(
        chunk_id="c1", document_id="doc-A", content="O motor funciona muito bem.", tokens_count=5, secao="Sec1", nome_arquivo="manual.pdf"
    )
    # chunk2 is made highly overlapping with chunk1 (Jaccard similarity will be 4/5 = 0.8 > 0.7)
    chunk2 = Chunk(
        chunk_id="c2", document_id="doc-A", content="motor funciona muito bem.", tokens_count=4, secao="Sec1", nome_arquivo="manual.pdf"
    )
    chunk3 = Chunk(
        chunk_id="c3", document_id="doc-B", content="Um assunto totalmente diferente sobre clima.", tokens_count=6, secao="Sec2", nome_arquivo="outro.pdf"
    )
    
    store = FakeVectorStore([chunk1, chunk2, chunk3])
    provider = FakeEmbeddingProvider()
    
    # Pure Vector mode
    retriever = HybridRetriever(vector_store=store, embedding_provider=provider, use_hybrid=False)
    
    # Retrieve top 2
    results = retriever.retrieve("Como funciona o motor?", filter_metadata={}, top_k=2)
    
    # Deduplication should drop chunk2 because it is highly redundant with chunk1.
    # Therefore, results should contain chunk1 and chunk3!
    assert len(results) == 2
    assert results[0].chunk.chunk_id == "c1"
    assert results[1].chunk.chunk_id == "c3"


def test_retriever_hybrid_rrf():
    chunk1 = Chunk(chunk_id="c1", document_id="doc-A", content="motor a combustão", tokens_count=3, secao="S1")
    chunk2 = Chunk(chunk_id="c2", document_id="doc-A", content="revisão do óleo", tokens_count=3, secao="S2")
    
    store = FakeVectorStore([chunk1, chunk2])
    provider = FakeEmbeddingProvider()
    
    retriever = HybridRetriever(vector_store=store, embedding_provider=provider, use_hybrid=True)
    
    results = retriever.retrieve("óleo combustão", filter_metadata={}, top_k=2)
    assert len(results) > 0


@patch("src.infrastructure.adapters.reranker.CrossEncoder")
def test_reranker_cross_encoder(mock_cross_encoder_cls):
    # Setup mock CrossEncoder
    mock_encoder = MagicMock()
    # Mock predict: returns high score for second item, low score for first
    mock_encoder.predict.return_value = [0.1, 0.95]
    mock_cross_encoder_cls.return_value = mock_encoder
    
    reranker = CrossEncoderReranker(model_name="fake-ranker")
    
    chunk1 = Chunk(chunk_id="c1", document_id="doc-A", content="Conteúdo não muito relevante.", tokens_count=5)
    chunk2 = Chunk(chunk_id="c2", document_id="doc-A", content="Conteúdo extremamente relevante sobre o motor.", tokens_count=6)
    
    results = [
        QueryResult(chunk=chunk1, score=0.8),
        QueryResult(chunk=chunk2, score=0.5)
    ]
    
    reranked = reranker.rerank("motor", results, top_k=2)
    
    # Check that sorting was updated based on cross-encoder output
    assert len(reranked) == 2
    assert reranked[0].chunk.chunk_id == "c2" # chunk2 should rank first now!
    assert reranked[0].score == 0.95
    assert reranked[1].chunk.chunk_id == "c1"
    assert reranked[1].score == 0.1


def test_context_builder():
    builder = SimpleContextBuilder(max_context_tokens=60) # realistic token budget for 2 small chunks
    
    chunk1 = Chunk(chunk_id="c1", document_id="doc-1", content="Primeira frase curta.", tokens_count=4, secao="Secão A", nome_arquivo="manual.pdf")
    chunk2 = Chunk(chunk_id="c2", document_id="doc-1", content="Segunda frase curta.", tokens_count=4, secao="Secão B", nome_arquivo="manual.pdf")
    chunk3 = Chunk(chunk_id="c3", document_id="doc-1", content="Terceira frase.", tokens_count=3, secao="Secão C", nome_arquivo="manual.pdf")
    
    results = [
        QueryResult(chunk=chunk1, score=0.9),
        QueryResult(chunk=chunk2, score=0.8),
        QueryResult(chunk=chunk3, score=0.7)
    ]
    
    context = builder.build_context("pergunta", results)
    
    # Verify that citations are present
    assert "[Fonte: Seção 'Secão A' no arquivo 'manual.pdf']" in context.context_text
    # Verify token clipping (not all chunks should fit, typically 2 will fit and 3rd will be discarded)
    assert len(context.used_chunks) == 2
    assert len(context.discarded_chunks) == 1


@patch("httpx.Client.post")
def test_llm_provider_retries_and_success(mock_post):
    # Mock httpx response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Resposta fictícia baseada no contexto."}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20}
    }
    
    # Set side-effects: first call fails (connection error), second succeeds
    mock_post.side_effect = [httpx.RequestError("Conexão falhou"), mock_response]
    
    provider = LMStudioLLMProvider()
    
    # We patch time.sleep to avoid waiting in tests
    with patch("time.sleep") as mock_sleep:
        ans = provider.generate_response(
            system_prompt="system",
            context="context text",
            user_query="user query"
        )
        
        assert ans == "Resposta fictícia baseada no contexto."
        # Verify post was called twice due to retry
        assert mock_post.call_count == 2
        # Verify sleep was called once with backoff 1.0
        mock_sleep.assert_called_once_with(1.0)
