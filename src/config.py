import os

class Settings:
    # API Settings
    API_KEY: str = os.getenv("API_KEY", "docurag_secret_api_key_v1")
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Path settings
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "data/uploads")
    QDRANT_PATH: str = os.getenv("QDRANT_PATH", "data/qdrant")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/docurag.db")
    LOGS_DIR: str = os.getenv("LOGS_DIR", "data/logs")
    
    # External Services
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    LM_STUDIO_URL: str = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "qwen/qwen3.5-9b")
    
    # AI Models
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-base")
    RERANK_MODEL_NAME: str = os.getenv("RERANK_MODEL_NAME", "BAAI/bge-reranker-base")
    
    # Processing configs
    CHUNK_SIZE_TARGET: int = int(os.getenv("CHUNK_SIZE_TARGET", "512"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "64"))
    
    # System Paths (OCR / Rendering Fallbacks)
    TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", "")
    POPPLER_PATH: str = os.getenv("POPPLER_PATH", "")

# Instantiate settings
settings = Settings()

# Ensure directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.QDRANT_PATH, exist_ok=True)
os.makedirs(settings.LOGS_DIR, exist_ok=True)
