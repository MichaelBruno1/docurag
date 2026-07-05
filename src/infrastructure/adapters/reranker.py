import logging
from typing import List, Optional
import torch
from sentence_transformers import CrossEncoder

from src.domain.entities import QueryResult
from src.domain.ports import Reranker
from src.config import settings
from src.infrastructure.adapters.device_utils import get_device

logger = logging.getLogger(__name__)

class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or settings.RERANK_MODEL_NAME
        self.device = get_device()
        
        logger.info(f"Inicializando CrossEncoderReranker com o modelo '{self._model_name}' no dispositivo '{self.device}'")
        try:
            self.model = CrossEncoder(self._model_name, device=self.device)
            logger.info("CrossEncoder carregado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao carregar o CrossEncoder {self._model_name} no dispositivo {self.device}: {e}. Tentando fallback para CPU.")
            try:
                self.device = "cpu"
                self.model = CrossEncoder(self._model_name, device="cpu")
                logger.info("CrossEncoder carregado na CPU como fallback.")
            except Exception as e2:
                logger.error(f"Falha total ao inicializar CrossEncoder: {e2}. Re-ranking operará como NO-OP (retornando similaridade original).")
                self.model = None

    def rerank(self, query: str, results: List[QueryResult], top_k: int) -> List[QueryResult]:
        if not results:
            return []
            
        if self.model is None:
            logger.warning("Reranker indisponível. Retornando os top_k com base na similaridade original.")
            return results[:top_k]
            
        logger.info(f"Reordenando {len(results)} chunks candidatos para a query: '{query}'")
        
        try:
            # Prepare pairs: [[query, doc1], [query, doc2] ...]
            pairs = [[query, res.chunk.content] for res in results]
            
            # Predict relevance scores (higher is more relevant)
            scores = self.model.predict(pairs)
            
            # Update scores in QueryResult
            reranked = []
            for idx, res in enumerate(results):
                # Update score with Cross-Encoder score
                res.score = float(scores[idx])
                reranked.append(res)
                
            # Sort descending by re-ranker score
            reranked.sort(key=lambda x: x.score, reverse=True)
            logger.info("Re-ranking concluído com sucesso.")
            return reranked[:top_k]
            
        except Exception as e:
            logger.error(f"Erro ao executar re-ranking: {e}. Retornando lista original.")
            return results[:top_k]
