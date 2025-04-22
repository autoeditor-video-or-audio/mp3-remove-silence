import os
import json
import logging
import pika
from datetime import datetime
from moviepy.editor import AudioFileClip

# Disable pika debug logs, setting them to WARNING or higher
logging.getLogger("pika").setLevel(logging.WARNING)

from services.minio_service import initialize_minio_client, postFileInBucket
from config import WORK_DIR, BUCKET_NAME, NOSILENCE_PREFIX, QUEUE_INPUT, QUEUE_OUTPUT
from utils.file_utils import create_directory, remove_temp_files
from services.silence_remover import remove_silence

logger = logging.getLogger(__name__)

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

def process_next_message():
    connection = initialize_rabbitmq_connection()
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_INPUT, durable=True)

    method_frame, header_frame, body = channel.basic_get(queue=QUEUE_INPUT, auto_ack=False)
    if method_frame:
        message = json.loads(body)
        filename = message.get("filename")        
        if not filename:
            logger.warning("Mensagem sem 'filename'. Ignorando.")
            channel.basic_ack(delivery_tag=method_frame.delivery_tag)
            return

        create_directory(WORK_DIR)
        local_path = os.path.join(WORK_DIR, filename)
        output_path = os.path.join(WORK_DIR, f"nosilence-{filename}")
        remote_path = f"{NOSILENCE_PREFIX}/{filename}"

        try:
            client = initialize_minio_client()
            subdir = message.get("subdir")
            logger.info(f"Baixando arquivo do bucket: {subdir}/{filename}")
            client.fget_object(BUCKET_NAME, f"{subdir}/{filename}", local_path)

            logger.info("Removendo silêncio...")
            remove_silence(local_path, output_path)

            clip = AudioFileClip(output_path)
            clip.write_audiofile(local_path)

            postFileInBucket(client, BUCKET_NAME, remote_path, local_path, 'audio/mpeg')

            message["file_name"] = f"nosilence-{filename}"
            message["bucket_path"] = remote_path
            message["process_no_silence_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            channel.queue_declare(queue=QUEUE_OUTPUT, durable=True)
            channel.basic_publish(
                exchange='',
                routing_key=QUEUE_OUTPUT,
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)
            )

            logger.info("Mensagem publicada na fila 01_audiocast.")
            channel.basic_ack(delivery_tag=method_frame.delivery_tag)

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")
            channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=False)

        finally:
            remove_temp_files(local_path, output_path)
            if filename and subdir:
                try:
                    client.remove_object(BUCKET_NAME, f"{subdir}/{filename}")
                    logger.info(f"Arquivo removido do bucket: {subdir}/{filename}")
                except Exception as e:
                    logger.warning(f"Falha ao remover o arquivo do bucket: {e}")
            connection.close()

    else:
        logger.info("Nenhuma mensagem na fila.")
        connection.close()
