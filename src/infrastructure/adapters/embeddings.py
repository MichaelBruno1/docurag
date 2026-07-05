import logging
from typing import List, Optional, Dict
import torch
from sentence_transformers import SentenceTransformer

from src.domain.ports import EmbeddingProvider
from src.config import settings
from src.infrastructure.adapters.device_utils import get_device

logger = logging.getLogger(__name__)

class SentenceTransformersEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or settings.EMBEDDING_MODEL_NAME
        
        # Detect GPU/CUDA/DirectML support
        self.device = get_device()
        logger.info(f"Inicializando SentenceTransformer('{self._model_name}') no dispositivo: {self.device}")
        
        try:
            self.model = SentenceTransformer(self._model_name, device=self.device)
            logger.info(f"Modelo de embedding carregado com sucesso. Dimensão: {self.dimension()}")
        except Exception as e:
            logger.error(f"Erro ao carregar o modelo de embedding {self._model_name} no dispositivo {self.device}: {e}. Tentando fallback na CPU.")
            self.device = "cpu"
            self.model = SentenceTransformer(self._model_name, device="cpu")
            
        # In-memory LRU-like cache for sentence/chunk embeddings
        self._cache: Dict[str, List[float]] = {}
        self._max_cache_size = 10000

    def get_embedding(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self.dimension()
            
        # Check cache
        if text in self._cache:
            return self._cache[text]
            
        # Compute and convert to list
        embedding = self.model.encode(text, convert_to_numpy=True)
        embedding_list = embedding.tolist()
        
        # Save to cache
        self._save_to_cache(text, embedding_list)
        return embedding_list

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
            
        results = []
        texts_to_compute = []
        indices_to_compute = []
        
        # Check cache first for batch items
        for i, text in enumerate(texts):
            if text in self._cache:
                results.append((i, self._cache[text]))
            else:
                texts_to_compute.append(text)
                indices_to_compute.append(i)
                
        # Compute non-cached items
        if texts_to_compute:
            embeddings = self.model.encode(texts_to_compute, convert_to_numpy=True, batch_size=32)
            for text, emb_arr, orig_idx in zip(texts_to_compute, embeddings, indices_to_compute):
                emb_list = emb_arr.tolist()
                self._save_to_cache(text, emb_list)
                results.append((orig_idx, emb_list))
                
        # Sort results by original index to preserve order
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

    def model_version(self) -> str:
        return self._model_name

    def dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def _save_to_cache(self, text: str, embedding: List[float]) -> None:
        if len(self._cache) >= self._max_cache_size:
            # Clear oldest 10% of cache if full
            logger.debug("Embedding cache cheio, limpando itens mais antigos.")
            keys_to_remove = list(self._cache.keys())[:int(self._max_cache_size * 0.1)]
            for k in keys_to_remove:
                self._cache.pop(k, None)
        self._cache[text] = embedding
