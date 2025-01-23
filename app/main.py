import os
import time
import subprocess
import shutil
from minio import Minio
from minio.error import S3Error
from utils import green, logger
import moviepy.editor as mp
from datetime import datetime
import pika
import json

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
    logger.debug(green(f"Mensagem publicada na fila {queue_name}: {message}"))
    connection.close()

# Verifica se o arquivo tem extensão .mp3
def verificar_extensao_arquivo_mp3(caminho_arquivo):
    _, extensao = os.path.splitext(caminho_arquivo)
    return extensao.lower() == ".mp3"

# Cria um diretório, caso ele não exista
def create_directory(path):
    try:
        os.makedirs(path)
        logger.debug(green(f"Diretório {path} criado com sucesso!"))
    except FileExistsError:
        logger.debug(green(f"Diretório {path} já existe."))

# Faz upload de arquivos para o bucket
def postFileInBucket(client, bucket_name, path_dest, path_src, content_type=None):
    if path_src.endswith('.txt'):
        content_type = 'text/plain'
    logger.debug(green(f"Fazendo upload no bucket {bucket_name}, arquivo {path_dest}"))
    client.fput_object(
        bucket_name,
        path_dest,
        path_src,
        content_type=content_type
    )
    logger.debug(green(f"Upload do arquivo {path_src} realizado com sucesso."))

# Baixa o primeiro arquivo MP3 encontrado apenas na raiz do bucket
def download_mp3_from_bucket(client, bucket_name):
    objects = client.list_objects(bucket_name, prefix="", recursive=False)
    for obj in objects:
        if verificar_extensao_arquivo_mp3(obj.object_name) and '/' not in obj.object_name:
            local_filename = obj.object_name.replace('\\', '/').split('/')[-1]
            logger.debug(green(f"Download: {obj.object_name}/{local_filename}"))
            client.fget_object(bucket_name, obj.object_name, f"/app/foredit/{local_filename}")
            logger.debug(green(f"{local_filename} Download realizado com sucesso."))
            return local_filename
    return None

# Processa o arquivo de áudio e vídeo (edição, conversão e upload para o bucket)
def process_audio_video(nameProcessedFile, client, bucketSet):
    # Cria diretório para arquivos editados
    pathDirFilesEdited = "/app/edited/"
    create_directory(pathDirFilesEdited)
    #################################
    # ARQUIVO ORIGINAL
    # Caminhos dos arquivos
    original_file_path = f"/app/foredit/{nameProcessedFile}"
    original_bucket_path = f"files-without-silence/original-{nameProcessedFile}"

    # Faz upload do arquivo original para o bucket
    postFileInBucket(client, bucketSet, original_bucket_path, original_file_path, 'audio/mpeg')

    # Publica o arquivo original no RabbitMQ
    original_file_info = {
        "file_format": "mp3",
        "file_name": nameProcessedFile,
        "bucket_path": original_bucket_path,
        "process_start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_type": "original"
    }
    publish_to_rabbitmq("01_mp3_to_video", original_file_info)

    #################################
    # BLEND MIXER
    # Caminhos dos arquivos
    original_file_path = f"/app/foredit/{nameProcessedFile}"
    original_bucket_path = f"audios-to-blend-mixer/original-{nameProcessedFile}"
    # Faz upload do arquivo original para o bucket
    postFileInBucket(client, bucketSet, original_bucket_path, original_file_path, 'audio/mpeg')

    # Publica o arquivo original no RabbitMQ
    original_file_info = {
        "file_format": "mp3",
        "file_name": nameProcessedFile,
        "bucket_path": original_bucket_path,
        "process_start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_type": "original"
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
    logger.debug(green(f"Editado: {nameProcessedFile}"))

    clip = mp.AudioFileClip(f"{pathDirFilesEdited}WithoutSilence-{nameProcessedFile}")
    clip.write_audiofile(f"{pathDirFilesEdited}{nameProcessedFile}")

    # Faz upload do arquivo processado para o bucket
    postFileInBucket(client, bucketSet, f"files-without-silence/{nameProcessedFile}", f"{pathDirFilesEdited}{nameProcessedFile}", 'audio/mpeg')

    # Publica na fila do RabbitMQ
    file_info = {
        "file_format": "mp3",
        "file_name": nameProcessedFile,
        "bucket_path": f"files-without-silence/{nameProcessedFile}",
        "process_start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    publish_to_rabbitmq("01_mp3_to_video", file_info)

    # Remove os diretórios temporários usados para edição
    shutil.rmtree(pathDirFilesEdited)
    shutil.rmtree("/app/foredit/")

    # Remove o arquivo original do bucket após o processamento
    client.remove_object(bucketSet, f"{nameProcessedFile}")
    logger.debug(green(f"Arquivo original removido do bucket: {nameProcessedFile}"))

# Loop contínuo para monitorar a pasta no MinIO
def monitor_and_process():
    TIME_SLEEP = int(os.getenv('TIME_SLEEP', 3))

    bucketSet = "autoeditor"
    client = initialize_minio_client()
    logger.debug(green(f'Monitorando bucket {bucketSet} - {datetime.now()}'))

    while True:
        try:
            nameProcessedFile = download_mp3_from_bucket(client, bucketSet)
            if nameProcessedFile:
                process_audio_video(nameProcessedFile, client, bucketSet)
            
        except S3Error as exc:
            logger.debug(green("Erro ocorrido: ", exc))
        time.sleep(TIME_SLEEP)  # Aguarda 3 segundos antes de verificar novamente

if __name__ == "__main__":
    monitor_and_process()
