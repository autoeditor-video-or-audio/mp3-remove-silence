import os
import logging

logger = logging.getLogger(__name__)

def create_directory(path):
    try:
        os.makedirs(path, exist_ok=True)
        logger.info(f"Diretório {path} criado com sucesso!")
    except Exception as e:
        logger.error(f"Erro ao criar diretório {path}: {e}")

def remove_temp_files(*filepaths):
    for path in filepaths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Arquivo removido: {path}")
        except Exception as e:
            logger.warning(f"Erro ao remover arquivo {path}: {e}")
