import sys
import logging
from redis import Redis
from rq import Worker
from src.config import settings

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger("docurag_worker")

def main():
    logger.info("Iniciando Worker do DocuRAG...")
    try:
        redis_conn = Redis.from_url(settings.REDIS_URL)
        # Test connection
        redis_conn.ping()
        logger.info(f"Conectado ao Redis em: {settings.REDIS_URL}")
    except Exception as e:
        logger.critical(f"Não foi possível conectar ao Redis no worker: {e}")
        sys.exit(1)
        
    worker = Worker(["docurag_tasks"], connection=redis_conn)
    logger.info("Aguardando novas tarefas na fila 'docurag_tasks'...")
    worker.work()

if __name__ == "__main__":
    main()
