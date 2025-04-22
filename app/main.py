# Este arquivo foi modularizado. A lógica foi movida para arquivos separados.

from services.rabbitmq_service import process_next_message
from logger_config import setup_logger
from config import WORK_DIR
from utils.file_utils import create_directory

logger = setup_logger()
create_directory(WORK_DIR)

if __name__ == "__main__":
    process_next_message()
