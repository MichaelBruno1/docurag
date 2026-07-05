import uvicorn
import logging
from src.config import settings

# Configure logging format to structured JSON to align with production monitoring systems
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='{"timestamp": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
)

logger = logging.getLogger("docurag_main")

def main():
    logger.info(f"Iniciando Servidor Web DocuRAG em {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "src.presentation.api:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=False  # Disabled in production for performance
    )

if __name__ == "__main__":
    main()
