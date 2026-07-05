import torch
import logging
from typing import Union, Any

logger = logging.getLogger(__name__)

def get_device() -> Union[str, Any]:
    """
    Detects and returns the best available computation device.
    Supports Nvidia CUDA, AMD ROCm (via "cuda" alias), and AMD DirectML (for native Windows).
    Falls back to "cpu" if no GPU acceleration is available.
    """
    # 1. Check for standard CUDA or ROCm (ROCm presents itself as CUDA in PyTorch)
    if torch.cuda.is_available():
        logger.info("GPU detectada e ativa via CUDA/ROCm.")
        return "cuda"
        
    # 2. Check for DirectML (crucial for native Windows AMD GPU acceleration)
    try:
        import torch_directml
        if torch_directml.is_available():
            logger.info("GPU AMD detectada e ativa via DirectML.")
            return torch_directml.device()
    except ImportError:
        logger.debug("Biblioteca torch-directml não encontrada. Pulando verificação DirectML.")
    except Exception as e:
        logger.warning(f"Erro ao inicializar DirectML: {e}")
        
    # 3. Fallback to CPU
    logger.info("Nenhuma GPU compatível localizada. Executando modelos em CPU.")
    return "cpu"
