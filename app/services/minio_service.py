# Funções relacionadas ao MinIO
import os
import logging
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

def initialize_minio_client():
    MINIO_URL = os.environ['MINIO_URL']
    MINIO_PORT = os.environ['MINIO_PORT']
    MINIO_ROOT_USER = os.environ['MINIO_ROOT_USER']
    MINIO_ROOT_PASSWORD = os.environ['MINIO_ROOT_PASSWORD']

    return Minio(
        f"{MINIO_URL}:{MINIO_PORT}",
        access_key=MINIO_ROOT_USER,
        secret_key=MINIO_ROOT_PASSWORD,
        secure=False,
    )

def postFileInBucket(client, bucket_name, path_dest, path_src, content_type=None):
    if path_src.endswith('.txt'):
        content_type = 'text/plain'
    logger.info(f"Fazendo upload no bucket {bucket_name}, arquivo {path_dest}")
    client.fput_object(
        bucket_name,
        path_dest,
        path_src,
        content_type=content_type
    )
    logger.info(f"Upload do arquivo {path_src} realizado com sucesso.")
