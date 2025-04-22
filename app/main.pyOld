import os
import time
import logging
import subprocess
import shutil
from minio import Minio
from minio.error import S3Error
import moviepy.editor as mp
from datetime import datetime
import pika
import json
from libs.transcription_utils import transcribe_audio_whisper, classify_transcription, get_categories_from_env

# Configuração do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable pika debug logs, setting them to WARNING or higher
logging.getLogger("pika").setLevel(logging.WARNING)

# Inicializa o cliente MinIO com variáveis de ambiente
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

# Inicializa a conexão com o RabbitMQ
def initialize_rabbitmq_connection():
    rabbitmq_host = os.getenv('RABBITMQ_HOST', '')
    rabbitmq_port = int(os.getenv('RABBITMQ_PORT', 5672))
    rabbitmq_vhost = os.getenv('RABBITMQ_VHOST', '/')
    rabbitmq_user = os.getenv('RABBITMQ_USER', '')
    rabbitmq_pass = os.getenv('RABBITMQ_PASS', '')

    credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
    return pika.BlockingConnection(pika.ConnectionParameters(
        host=rabbitmq_host,
        port=rabbitmq_port,
        virtual_host=rabbitmq_vhost,
        credentials=credentials
    ))

# Publica mensagem na fila do RabbitMQ
def publish_to_rabbitmq(queue_name, message):
    connection = initialize_rabbitmq_connection()
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)
    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,  # Persistente
        )
    )
    logger.info(f"Mensagem publicada na fila {queue_name}: {message}")
    connection.close()

# Verifica se o arquivo tem extensão .mp3
def verificar_extensao_arquivo_mp3(caminho_arquivo):
    _, extensao = os.path.splitext(caminho_arquivo)
    return extensao.lower() == ".mp3"

# Cria um diretório, caso ele não exista
def create_directory(path):
    try:
        os.makedirs(path)
        logger.info(f"Diretório {path} criado com sucesso!")
    except FileExistsError:
        logger.info(f"Diretório {path} já existe.")

# Faz upload de arquivos para o bucket
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

# Baixa o primeiro arquivo MP3 encontrado apenas na raiz do bucket
def download_mp3_from_bucket(client, bucket_name):
    objects = client.list_objects(bucket_name, prefix="", recursive=False)
    for obj in objects:
        if verificar_extensao_arquivo_mp3(obj.object_name) and '/' not in obj.object_name:
            local_filename = obj.object_name.replace('\\', '/').split('/')[-1]
            logger.info(f"Download: {obj.object_name}/{local_filename}")
            client.fget_object(bucket_name, obj.object_name, f"/app/foredit/{local_filename}")
            logger.info(f"{local_filename} Download realizado com sucesso.")
            return local_filename
    return None

# Processa o arquivo de áudio e vídeo (edição, conversão e upload para o bucket)
def process_audio_video(nameProcessedFile, client, bucketSet):
    # Cria diretório para arquivos editados
    pathDirFilesEdited = "/app/foredit/"
    create_directory(pathDirFilesEdited)

    #################################
    # TRANSCRIÇÃO
    API_TRANSCRIBE_URL = f"http://{os.getenv('API_TRANSCRIBE_URL')}:{os.getenv('API_TRANSCRIBE_PORT')}/asr"
    API_TRANSCRIBE_TIMEOUT = int(os.getenv('API_TRANSCRIBE_TIMEOUT', 1200))
    transcription_data = transcribe_audio_whisper(f"{pathDirFilesEdited}{nameProcessedFile}", API_TRANSCRIBE_URL, API_TRANSCRIBE_TIMEOUT)
    if not transcription_data:
        logger.error("Erro na transcrição. Processo abortado.")
        return False
    transcription_text = transcription_data.get("text", " ".join(segment["text"] for segment in transcription_data.get("segments", [])))

    # Obter categorias do ambiente
    categories = get_categories_from_env()
    # Classificar transcrição
    category = classify_transcription(transcription_text, categories)
    if not category:
        logger.warning("Classificação falhou. Categoria não será incluída.")
        category = "unknown"

    #################################
    # ARQUIVO ORIGINAL
    # Caminhos dos arquivos
    original_file_path = f"{pathDirFilesEdited}{nameProcessedFile}"
    original_bucket_path = f"processed-audios/original-{nameProcessedFile}"
    # Faz upload do arquivo original para o bucket
    postFileInBucket(client, bucketSet, original_bucket_path, original_file_path, 'audio/mpeg')
    # Publica o arquivo original no RabbitMQ
    original_file_info = {
        "file_format": "mp3",
        "file_name": f"original-{nameProcessedFile}",
        "bucket_path": original_bucket_path,
        "process_start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_type": "original",
        "category": category
    }
    publish_to_rabbitmq("02_mp3_to_video", original_file_info)

    #################################
    # BLEND MIXER
    # Caminhos dos arquivos
    original_bucket_path = f"audios-to-blend-mixer/{nameProcessedFile}"
    # Faz upload do arquivo original para o bucket
    postFileInBucket(client, bucketSet, original_bucket_path, original_file_path, 'audio/mpeg')
    # Publica o arquivo original no RabbitMQ
    original_file_info = {
        "file_format": "mp3",
        "file_name": nameProcessedFile,
        "bucket_path": original_bucket_path,
        "process_start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_type": "original",
        "category": category,  # Inclui a categoria
    }
    publish_to_rabbitmq("01_audio_to_blend_mixer", original_file_info)

    #################################
    # REMOVIDO O SILENCIO
    # Edita o vídeo para remover silêncios
    margin = os.getenv("AUTO_EDITOR_MARGIN", "0.04sec")
    subprocess.run([
        "auto-editor", 
        f"./foredit/{nameProcessedFile}",
        "--margin", margin,
        "-o", f"{pathDirFilesEdited}WithoutSilence-{nameProcessedFile}"
    ])
    logger.info(f"Editado: {nameProcessedFile}")

    clip = mp.AudioFileClip(f"{pathDirFilesEdited}WithoutSilence-{nameProcessedFile}")
    clip.write_audiofile(f"{pathDirFilesEdited}{nameProcessedFile}")

    # Faz upload do arquivo processado para o bucket
    postFileInBucket(client, bucketSet, f"files-without-silence/{nameProcessedFile}", f"{pathDirFilesEdited}{nameProcessedFile}", 'audio/mpeg')

    # Publica na fila do RabbitMQ
    file_info = {
        "file_format": "mp3",
        "file_name": nameProcessedFile,
        "bucket_path": f"files-without-silence/{nameProcessedFile}",
        "process_start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "category": category
    }
    publish_to_rabbitmq("01_mp3_to_video", file_info)

    # Remove os diretórios temporários usados para edição
    shutil.rmtree(pathDirFilesEdited)

    # Remove o arquivo original do bucket após o processamento
    client.remove_object(bucketSet, f"{nameProcessedFile}")
    logger.info(f"Arquivo original removido do bucket: {nameProcessedFile}")
    logger.info("...\o/...")

# Loop contínuo para monitorar a pasta no MinIO
def monitor_and_process():
    TIME_SLEEP = int(os.getenv('TIME_SLEEP', 3))

    bucketSet = "autoeditor"
    client = initialize_minio_client()
    logger.info(f'Monitorando bucket: {bucketSet} \o/')

    while True:
        try:
            nameProcessedFile = download_mp3_from_bucket(client, bucketSet)
            if nameProcessedFile:
                process_audio_video(nameProcessedFile, client, bucketSet)
            
        except S3Error as exc:
            logger.info("Erro ocorrido: ", exc)
        time.sleep(TIME_SLEEP)  # Aguarda 3 segundos antes de verificar novamente

if __name__ == "__main__":
    monitor_and_process()
