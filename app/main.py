import os
import subprocess
import shutil
from minio import Minio
from minio.error import S3Error
from utils import green, logger
import numpy as np
import moviepy.editor as mp
from moviepy.editor import AudioFileClip, VideoClip
from datetime import datetime

current_datetime = datetime.now()
currentAction = current_datetime.strftime("%d-%m-%Y--%H-%M-%S")

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

# Verifica se o arquivo tem extensão .mp3
def verificar_extensao_arquivo_mp3(caminho_arquivo):
    _, extensao = os.path.splitext(caminho_arquivo)
    return extensao.lower() == ".mp3"

# Converte MP3 para MP4
def converter_mp3_para_mp4(caminho_origem_mp3, caminho_destino_mp4, fps=25):
    # Carrega o arquivo de áudio MP3
    audio_clip = AudioFileClip(caminho_origem_mp3)

    # Cria um vídeo em branco com a mesma duração do áudio
    frame = np.zeros((1920, 1080, 3), dtype=np.uint8) + 255  # imagem branca
    video_clip = VideoClip(lambda t: frame, duration=audio_clip.duration)
    video_clip = video_clip.set_fps(fps).set_audio(audio_clip)

    # Salva o arquivo MP4 resultante
    video_clip.write_videofile(caminho_destino_mp4, codec='libx264', audio_codec='aac', temp_audiofile='temp-audio.m4a', remove_temp=True)
    logger.debug(green(f"Arquivo convertido para {caminho_destino_mp4}"))

# Cria um diretório, caso ele não exista
def create_directory(path):
    try:
        os.makedirs(path)
        logger.debug(green(f"Diretório {path} criado com sucesso!"))
    except FileExistsError:
        logger.debug(green(f"Diretório {path} já existe."))

# Função para fazer upload de arquivos para o bucket
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
        logger.debug(green(f"Download: {obj.object_name}"))
        if verificar_extensao_arquivo_mp3(obj.object_name) and '/' not in obj.object_name:
            local_filename = obj.object_name.replace('\\', '/').split('/')[-1]
            client.fget_object(bucket_name, obj.object_name, f"/app/foredit/{local_filename}")
            logger.debug(green(f"{local_filename} Download realizado com sucesso."))
            return local_filename
    return None

# Processa o arquivo de áudio e vídeo (edição, conversão e upload para o bucket)
def process_audio_video(nameProcessedFile, client, bucketSet):
    nameProcessedFileMp4 = nameProcessedFile[:-4] + ".mp4"

    # Converte MP3 para MP4
    converter_mp3_para_mp4(f"/app/foredit/{nameProcessedFile}", f"/app/foredit/{nameProcessedFileMp4}")

    # Cria diretório para arquivos editados
    pathDirFilesEdited = "/app/edited/"
    create_directory(pathDirFilesEdited)

    # Edita o vídeo para remover silêncios
    margin = os.getenv("AUTO_EDITOR_MARGIN", "0.04sec")
    subprocess.run([
        "auto-editor", 
        f"./foredit/{nameProcessedFileMp4}",
        "--margin", margin,
        "-o", f"{pathDirFilesEdited}WithoutSilence-{nameProcessedFileMp4}"
    ])
    logger.debug(green(f"Editado: {nameProcessedFile}"))

    # Reconverte MP4 para MP3
    clip = mp.AudioFileClip(f"{pathDirFilesEdited}WithoutSilence-{nameProcessedFileMp4}")
    clip.write_audiofile(f"{pathDirFilesEdited}{nameProcessedFile}")

    # Faz upload do arquivo processado para o bucket
    postFileInBucket(client, bucketSet, f"files-without-silence/{nameProcessedFile}", f"{pathDirFilesEdited}{nameProcessedFile}", 'audio/mpeg')
    # postFileInBucket(client, bucketSet, f"processing/step1/{currentAction}/Original-{nameProcessedFile}", f"/app/foredit/{nameProcessedFile}", 'audio/mpeg')

    # Remove diretórios temporários
    shutil.rmtree(pathDirFilesEdited)
    shutil.rmtree("/app/foredit/")
    shutil.rmtree("/app/edited/")

    # Remove o arquivo original do bucket
    client.remove_object(bucketSet, f"{nameProcessedFile}")
    logger.debug(green(f"Vídeo removido do bucket: {nameProcessedFile}"))

# Função principal
def main():
    bucketSet = "autoeditor"
    client = initialize_minio_client()

    logger.debug(green(f'...START -> {currentAction}'))

    # Tenta baixar o primeiro arquivo MP3 do bucket
    nameProcessedFile = download_mp3_from_bucket(client, bucketSet)

    if nameProcessedFile:
        # Processa o arquivo se encontrado
        process_audio_video(nameProcessedFile, client, bucketSet)
    else:
        logger.debug(green(f"Nenhum arquivo MP3 encontrado no bucket {bucketSet}"))

    logger.debug(green('...FINISHED...'))

if __name__ == "__main__":
    try:
        main()
    except S3Error as exc:
        logger.debug(green("Erro ocorrido: ", exc))
