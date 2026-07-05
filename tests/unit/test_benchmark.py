import pytest
import os
import json
from unittest.mock import MagicMock, patch

from src.domain.entities import Chunk, QueryResult
from src.infrastructure.adapters.benchmark_runner import AutomatedBenchmarkRunner

class FakeRetriever:
    def __init__(self, chunk):
        self.chunk = chunk
    def retrieve(self, query, filter_metadata, top_k):
        return [QueryResult(chunk=self.chunk, score=0.9)]

class FakeReranker:
    def rerank(self, query, results, top_k):
        return results[:top_k]

class FakeContextBuilder:
    def build_context(self, query, results):
        class FakeContext:
            context_text = results[0].chunk.content if results else ""
        return FakeContext()

class FakeLLMProvider:
    def __init__(self, response):
        self.response = response
    def generate_response(self, system_prompt, context, user_query):
        return self.response


def test_benchmark_runner_grounding_heuristics():
    runner = AutomatedBenchmarkRunner(None, None, None, None, None)
    
    # 1. High grounding: all entities in response exist in context
    context = "O motor X100 opera a 90 graus Celsius com óleo sintético."
    response = "O motor X100 opera a 90 graus."
    assert runner._verify_grounding(response, context) == 1.0
    
    # 2. Low/Partial grounding: new entities (hallucinations) added in response
    # '990' and 'Alemão' do not exist in the context, but 'Celsius' does
    response_hallucinated = "O motor Alemão X100 opera a 990 graus Celsius."
    score = runner._verify_grounding(response_hallucinated, context)
    assert score < 1.0
    assert score > 0.0
    
    # 3. Ignorance admission response checks
    # If no context exists, and LLM admits ignorance, score is 1.0 (valid)
    assert runner._verify_grounding("Não foi possível encontrar essa informação.", "") == 1.0


def test_benchmark_run_metrics_calculation(tmp_path):
    # Setup test file paths in temp directory to avoid disk pollution
    golden_file = tmp_path / "golden_set.json"
    history_file = tmp_path / "history.json"
    report_file = tmp_path / "report.md"
    
    # Write a mini 2-question golden set (1 positive, 1 negative)
    golden_data = [
        {
            "id": "q1",
            "question": "Qual a voltagem?",
            "expected_document": "manual.pdf",
            "expected_section": "Elétrica",
            "is_negative": False
        },
        {
            "id": "q2",
            "question": "Quem descobriu a América?",
            "is_negative": True
        }
    ]
    with open(golden_file, "w", encoding="utf-8") as f:
        json.dump(golden_data, f)
        
    # Setup fake pipeline components
    target_chunk = Chunk(
        chunk_id="c1",
        document_id="d1",
        content="A voltagem nominal é de 220V monofásico.",
        tokens_count=10,
        secao="Elétrica",
        nome_arquivo="manual.pdf"
    )
    
    retriever = FakeRetriever(target_chunk)
    reranker = FakeReranker()
    context_builder = FakeContextBuilder()
    
    # We subclass FakeLLMProvider to support multiple outputs
    class MultiLLMProvider:
        def generate_response(self, system_prompt, context, user_query):
            if "descobriu" in user_query:
                return "Não encontrou essa informação nos documentos."
            return "A voltagem é de 220V."
            
    runner = AutomatedBenchmarkRunner(
        retriever=retriever,
        reranker=reranker,
        context_builder=context_builder,
        llm_provider=MultiLLMProvider(),
        vector_store=MagicMock(),
        golden_set_path=str(golden_file),
        history_path=str(history_file),
        report_path=str(report_file)
    )
    
    run_result = runner.run_benchmark(config_label="Config Teste")
    
    # Verify aggregated averages
    avg = run_result["average_metrics"]
    assert avg["retrieval"]["hit_rate"] == 1.0  # target chunk was rank 1
    assert avg["retrieval"]["mrr"] == 1.0
    assert avg["retrieval"]["ndcg"] == 1.0
    assert avg["generation"]["ignorance_admission_rate"] == 1.0  # correctly admitted q2
    assert avg["generation"]["grounding_accuracy"] == 1.0  # 220V exists in context
    
    # Check that comparative markdown report was created
    assert os.path.exists(report_file)
    with open(report_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "Config Teste" in content
        assert "Hit Rate" in content
