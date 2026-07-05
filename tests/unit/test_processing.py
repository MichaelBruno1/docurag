import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from src.domain.entities import ParsedDocument, ParsedSection, Chunk
from src.infrastructure.adapters.enricher import YakeEnricher
from src.infrastructure.adapters.chunker import HybridChunker
from src.infrastructure.adapters.embeddings import SentenceTransformersEmbeddingProvider

# Fake Embedding Provider for lightweight CPU chunker tests
class FakeEmbeddingProvider:
    def get_embedding(self, text: str):
        return [0.5, 0.1, 0.1]
        
    def get_embeddings(self, texts: list):
        results = []
        for idx, t in enumerate(texts):
            if "diferente" in t.lower():
                results.append([0.1, 0.9, 0.1]) # Dissimilar vector
            else:
                results.append([0.5, 0.1, 0.1])
        return results
        
    def model_version(self) -> str:
        return "fake-e5-base"
        
    def dimension(self) -> int:
        return 3


def test_yake_enricher():
    enricher = YakeEnricher()
    
    doc = ParsedDocument(
        document_id="doc-yake",
        source_format="TXT",
        title="Manual de Instruções e Diretrizes Técnicas do Motor A",
        sections=[
            ParsedSection(
                heading="Introdução",
                level=2,
                content="Este manual de diretrizes técnicas apresenta o funcionamento básico do motor. Para ligar o equipamento, siga os passos descritos adiante."
            )
        ],
        raw_metadata={"author": "Eng. Silva", "created_at": "2026-07-04T12:00:00"}
    )
    
    enriched = enricher.enrich(doc)
    
    # Check taxonomy classification (should match "Manual")
    assert enriched.raw_metadata["categoria"] == "Manual"
    assert enriched.raw_metadata["autor"] == "Eng. Silva"
    assert enriched.raw_metadata["data_original"] == "2026-07-04T12:00:00"
    assert enriched.raw_metadata["idioma"] == "pt-BR"
    
    # Check keyword extraction with substring check
    assert len(enriched.sections[0].keywords) > 0
    assert any("manual" in kw.lower() or "diretriz" in kw.lower() for kw in enriched.sections[0].keywords)


def test_hybrid_chunker_structural_and_semantic():
    fake_provider = FakeEmbeddingProvider()
    chunker = HybridChunker(embedding_provider=fake_provider, target_size=50, overlap=10)
    
    # Section with text that needs semantic splitting (dissimilar sentence in the middle)
    doc = ParsedDocument(
        document_id="doc-chunk",
        source_format="TXT",
        title="Especificação do Motor",
        sections=[
            ParsedSection(
                heading="Capítulo 1",
                level=2,
                content="O motor funciona com combustão interna. Esta é a primeira frase do bloco de introdução. Agora temos um assunto completamente diferente aqui. Voltamos ao assunto do motor de combustão interna. E terminamos a explicação estrutural do motor.",
            )
        ],
        raw_metadata={"categoria": "Especificação Técnica"}
    )
    
    chunks = chunker.chunk(doc)
    
    assert len(chunks) > 1
    # Check that chunks are sequentially linked
    assert chunks[0].chunk_seguinte_id == chunks[1].chunk_id
    assert chunks[1].chunk_anterior_id == chunks[0].chunk_id
    
    # Check deterministic chunk_id (re-running generates same IDs)
    chunks_second_run = chunker.chunk(doc)
    assert chunks[0].chunk_id == chunks_second_run[0].chunk_id
    
    # Check parent section relationship propagation
    assert chunks[0].chunk_pai_id == "Capítulo 1"
    assert chunks[0].secao == "Capítulo 1"


def test_hybrid_chunker_adaptive_table():
    fake_provider = FakeEmbeddingProvider()
    # Reduced target_size from 60 to 25 to force splitting
    chunker = HybridChunker(embedding_provider=fake_provider, target_size=25, overlap=5)
    
    # Large Excel grid to split by rows
    grid = [
        ["Nome", "Idade", "Cargo"],
        ["Ana", "30", "Engenheira"],
        ["Bruno", "25", "Analista"],
        ["Carlos", "40", "Diretor"],
        ["Daniela", "35", "Gerente"]
    ]
    
    doc = ParsedDocument(
        document_id="doc-table",
        source_format="XLSX",
        title="Lista de Funcionários",
        sections=[
            ParsedSection(
                heading="Aba 1",
                level=2,
                content="",
                tables=[grid]
            )
        ]
    )
    
    chunks = chunker.chunk(doc)
    assert len(chunks) > 1
    
    # Confirm that headers row is duplicated in every split chunk
    for chunk in chunks:
        assert "| Nome | Idade | Cargo |" in chunk.content
        assert "| --- | --- | --- |" in chunk.content


@patch("src.infrastructure.adapters.embeddings.SentenceTransformer")
def test_embedding_provider_cache(mock_transformer_cls):
    # Setup mock transformer that mimics real SentenceTransformers numpy outputs
    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension.return_value = 128
    
    # Custom side-effect mapping to simulate 1D or 2D numpy arrays
    def mock_encode(sentences, *args, **kwargs):
        if isinstance(sentences, str):
            return np.array([0.1] * 128)
        else:
            return np.array([[0.1] * 128] * len(sentences))
            
    mock_transformer.encode.side_effect = mock_encode
    mock_transformer_cls.return_value = mock_transformer
    
    provider = SentenceTransformersEmbeddingProvider(model_name="fake-model")
    
    # First encoding: should hit the model
    emb1 = provider.get_embedding("Texto único para testar o cache.")
    assert len(emb1) == 128
    assert mock_transformer.encode.call_count == 1
    
    # Second encoding of same text: should hit cache (no model call)
    emb2 = provider.get_embedding("Texto único para testar o cache.")
    assert emb1 == emb2
    assert mock_transformer.encode.call_count == 1
    
    # Batch encoding: should use cache + model for new items
    embs = provider.get_embeddings(["Texto único para testar o cache.", "Outro texto novo."])
    assert len(embs) == 2
    assert len(embs[0]) == 128
    assert len(embs[1]) == 128
    # Model should only be encode "Outro texto novo."
    assert mock_transformer.encode.call_count == 2
