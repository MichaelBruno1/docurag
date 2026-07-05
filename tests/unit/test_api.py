import pytest
import io
import uuid
import datetime
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.config import settings
from src.domain.entities import Document, Chunk, QueryResult
from src.presentation.api import app

# API Key used in settings
API_KEY = settings.API_KEY

@pytest.fixture
def mock_pipeline_dependencies():
    # Patch all heavy pipeline dependencies instantiated during FastAPI lifespan
    with patch("src.presentation.api.SQLiteDocumentRepository") as mock_db_cls, \
         patch("src.presentation.api.QdrantVectorStore") as mock_vs_cls, \
         patch("src.presentation.api.SentenceTransformersEmbeddingProvider") as mock_emb_cls, \
         patch("src.presentation.api.CrossEncoderReranker") as mock_rank_cls, \
         patch("src.presentation.api.LMStudioLLMProvider") as mock_llm_cls, \
         patch("src.presentation.api.AutomatedBenchmarkRunner") as mock_bench_cls, \
         patch("src.presentation.api.Queue") as mock_queue_cls, \
         patch("src.presentation.api.Redis") as mock_redis_cls:
         
        # Instantiate mocks
        mock_db = MagicMock()
        mock_vs = MagicMock()
        mock_emb = MagicMock()
        mock_rank = MagicMock()
        mock_llm = MagicMock()
        mock_bench = MagicMock()
        mock_queue = MagicMock()
        mock_redis = MagicMock()
        
        mock_db_cls.return_value = mock_db
        mock_vs_cls.return_value = mock_vs
        mock_emb_cls.return_value = mock_emb
        mock_rank_cls.return_value = mock_rank
        mock_llm_cls.return_value = mock_llm
        mock_bench_cls.return_value = mock_bench
        mock_queue_cls.return_value = mock_queue
        mock_redis_cls.return_value = mock_redis
        
        # Setup get_stats return values
        mock_db.get_stats.return_value = {"total_documents": 0, "total_bytes": 0, "status_counts": {}}
        mock_vs.get_stats.return_value = {"total_chunks": 0, "collection_status": "empty"}
        
        # Setup mock embeddings, LLM, and reranker returns to satisfy pipeline flow
        mock_emb.get_embedding.return_value = [0.1, 0.2, 0.3]
        mock_llm.generate_response.return_value = "Resposta mockada da LLM."
        mock_rank.rerank.side_effect = lambda query, results, top_k: results[:top_k]
        
        yield {
            "db": mock_db,
            "vs": mock_vs,
            "emb": mock_emb,
            "rank": mock_rank,
            "llm": mock_llm,
            "bench": mock_bench,
            "queue": mock_queue,
            "redis": mock_redis
        }


def test_health_endpoint(mock_pipeline_dependencies):
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "sqlite" in data["services"]
        assert "qdrant" in data["services"]


def test_api_key_security_rejection(mock_pipeline_dependencies):
    with TestClient(app) as client:
        # Request stats without API Key
        response = client.get("/stats")
        assert response.status_code == 403
        
        # Request stats with wrong API Key
        response = client.get("/stats", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 403
        assert response.json()["detail"] == "Não autorizado: Chave de API inválida."


def test_get_stats_authorized(mock_pipeline_dependencies):
    mock_db = mock_pipeline_dependencies["db"]
    mock_db.list_documents.return_value = []
    
    with TestClient(app) as client:
        response = client.get("/stats", headers={"X-API-Key": API_KEY})
        assert response.status_code == 200
        data = response.json()
        assert "database_stats" in data
        assert "vector_store_stats" in data
        assert data["documents"] == []


def test_get_document_status_flow(mock_pipeline_dependencies):
    mock_db = mock_pipeline_dependencies["db"]
    doc_id = str(uuid.uuid4())
    
    # Mock database return for document status
    mock_db.get_document.side_effect = lambda x: Document(
        document_id=x,
        nome_arquivo="contrato.pdf",
        formato="PDF",
        tamanho_bytes=2048,
        created_at=datetime.datetime.utcnow(),
        status="concluido",
        categoria="Contrato"
    ) if x == doc_id else None
    
    with TestClient(app) as client:
        # Invalid document id
        response = client.get(f"/documents/invalid-id", headers={"X-API-Key": API_KEY})
        assert response.status_code == 404
        
        # Valid document id
        response = client.get(f"/documents/{doc_id}", headers={"X-API-Key": API_KEY})
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == doc_id
        assert data["status"] == "concluido"
        assert data["categoria"] == "Contrato"


def test_delete_document_flow(mock_pipeline_dependencies):
    mock_db = mock_pipeline_dependencies["db"]
    mock_vs = mock_pipeline_dependencies["vs"]
    doc_id = str(uuid.uuid4())
    
    # Mock document in db
    mock_db.get_document.side_effect = lambda x: Document(
        document_id=x,
        nome_arquivo="relatorio.docx",
        formato="DOCX",
        tamanho_bytes=1024,
        created_at=datetime.datetime.utcnow(),
        status="concluido"
    ) if x == doc_id else None
    
    with TestClient(app) as client:
        # Delete document
        response = client.delete(f"/documents/{doc_id}", headers={"X-API-Key": API_KEY})
        assert response.status_code == 200
        assert response.json()["detail"] == "Documento removido com sucesso de todas as camadas de armazenamento."
        
        # Verify deletions were called
        mock_vs.delete_document_chunks.assert_called_once_with(doc_id)
        mock_db.delete_document.assert_called_once_with(doc_id)


def test_ingest_document_validation_and_enqueue(mock_pipeline_dependencies):
    mock_queue = mock_pipeline_dependencies["queue"]
    
    with TestClient(app) as client:
        # 1. Reject unsupported formats (e.g. image.png)
        file_png = io.BytesIO(b"dummy image data")
        response = client.post(
            "/documents/ingest",
            files={"file": ("image.png", file_png, "image/png")},
            headers={"X-API-Key": API_KEY}
        )
        assert response.status_code == 400
        assert "não suportado" in response.json()["detail"]
        
        # 2. Accept valid text format (e.g. manual.txt) and enqueue
        file_txt = io.BytesIO(b"Este e o conteudo do manual corporativo.")
        # Patch os.remove to prevent file clean up errors if test runs in sandbox
        with patch("os.path.exists", return_value=True), patch("os.remove") as mock_remove:
            response = client.post(
                "/documents/ingest",
                files={"file": ("manual.txt", file_txt, "text/plain")},
                headers={"X-API-Key": API_KEY}
            )
            assert response.status_code == 202
            data = response.json()
            assert "document_id" in data
            assert data["nome_arquivo"] == "manual.txt"
            assert data["status"] == "enfileirado"
            
            # Verify RQ enqueuing occurred
            mock_queue.enqueue.assert_called_once()
            args, kwargs = mock_queue.enqueue.call_args
            assert args[0] == "src.infrastructure.queue.tasks.process_document_task"
            assert args[2] == "manual.txt" # filename
            assert args[3] == data["document_id"] # document_id


def test_query_rag_endpoint(mock_pipeline_dependencies):
    mock_vs = mock_pipeline_dependencies["vs"]
    mock_llm = mock_pipeline_dependencies["llm"]
    
    # Mock retrieval hits
    chunk1 = Chunk(chunk_id="c1", document_id="d1", content="Como ligar o motor: ligue na tomada.", tokens_count=10, secao="Manual", nome_arquivo="manual.txt")
    mock_vs.search_similarity.return_value = [QueryResult(chunk=chunk1, score=0.95)]
    
    # LLM Mock response content
    mock_llm.generate_response.return_value = "Ligue o motor conectando-o à tomada."
    
    with TestClient(app) as client:
        response = client.post(
            "/query",
            json={"query": "Como ligar o motor?", "top_k": 3},
            headers={"X-API-Key": API_KEY}
        )
        assert response.status_code == 200
        data = response.json()
        assert "trace_id" in data
        assert data["response"] == "Ligue o motor conectando-o à tomada."
        assert len(data["used_chunks"]) == 1
        assert data["used_chunks"][0]["chunk_id"] == "c1"


def test_benchmark_endpoints(mock_pipeline_dependencies):
    mock_bench = mock_pipeline_dependencies["bench"]
    
    # 1. Setup mock run_benchmark return
    mock_bench.run_benchmark.return_value = {
        "timestamp": "2026-07-05T00:00:00",
        "average_metrics": {
            "retrieval": {"hit_rate": 0.9, "mrr": 0.85},
            "generation": {"grounding_accuracy": 0.95}
        }
    }
    mock_bench.history_path = "data/benchmark_history_json_mock"
    
    with TestClient(app) as client:
        # Run benchmark
        response = client.post("/benchmark/run?config_label=TesteMock", headers={"X-API-Key": API_KEY})
        assert response.status_code == 200
        data = response.json()
        assert "TesteMock" in data["message"]
        assert data["average_metrics"]["retrieval"]["hit_rate"] == 0.9
        mock_bench.run_benchmark.assert_called_with(config_label="TesteMock", num_questions=30)

        # Run benchmark with custom num_questions
        response = client.post("/benchmark/run?config_label=TesteMock&num_questions=15", headers={"X-API-Key": API_KEY})
        assert response.status_code == 200
        mock_bench.run_benchmark.assert_called_with(config_label="TesteMock", num_questions=15)
        
        # Get benchmark results history (file doesn't exist yet)
        with patch("os.path.exists", return_value=False):
            response = client.get("/benchmark/results", headers={"X-API-Key": API_KEY})
            assert response.status_code == 200
            assert response.json() == []
            
        # Get benchmark results history (file exists)
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open := MagicMock()):
            # Mock reading a JSON history list
            mock_file = MagicMock()
            mock_file.read.return_value = '[{"config_label": "TesteMock"}]'
            mock_open.return_value.__enter__.return_value = mock_file
            
            response = client.get("/benchmark/results", headers={"X-API-Key": API_KEY})
            assert response.status_code == 200
            assert len(response.json()) == 1
            assert response.json()[0]["config_label"] == "TesteMock"


def test_query_rag_boundary_validations(mock_pipeline_dependencies):
    with TestClient(app) as client:
        # Query too short (less than 3 characters)
        response = client.post(
            "/query",
            json={"query": "Oi", "top_k": 3},
            headers={"X-API-Key": API_KEY}
        )
        assert response.status_code == 422
        
        # top_k too large (greater than 15)
        response = client.post(
            "/query",
            json={"query": "Como ligar o motor?", "top_k": 20},
            headers={"X-API-Key": API_KEY}
        )
        assert response.status_code == 422

        # top_k too small (less than 1)
        response = client.post(
            "/query",
            json={"query": "Como ligar o motor?", "top_k": 0},
            headers={"X-API-Key": API_KEY}
        )
        assert response.status_code == 422

