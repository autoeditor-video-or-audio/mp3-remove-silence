import os
import logging
import requests
from datetime import datetime
from pydub import AudioSegment

logger = logging.getLogger(__name__)

CATEGORY_PROMPT = """
Com base na transcrição abaixo, escolha a categoria que melhor descreve o conteúdo entre as seguintes opções: CATEGORIES.
Responda exclusivamente com o nome de uma das categorias. Não forneça explicações adicionais.
Transcrição: TRANSCRIBE
"""

def transcribe_audio_whisper(file_path, api_url, api_timeout):
    """Transcreve o áudio usando Whisper API."""
    logger.info("Iniciando a transcrição do áudio.")
    try:
        headers = {'accept': 'application/json'}
        logger.info(f"Enviando arquivo {file_path} para o servidor de transcrição.")
        files = {'audio_file': open(file_path, 'rb')}
        response = requests.post(api_url, headers=headers, files=files, timeout=api_timeout)

        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')

            if "application/json" in content_type:
                return response.json()
            elif "text/plain" in content_type or content_type.startswith("text/"):
                logger.info("Resposta em texto puro detectada.")
                return {"text": response.text.strip()}
            else:
                logger.error(f"Tipo de conteúdo inesperado: {content_type}. Resposta: {response.text}")
                return None
        else:
            logger.error(f"Erro na transcrição: Status {response.status_code}. Resposta: {response.text}")
            return None
    except requests.RequestException as e:
        logger.error(f"Erro durante a solicitação para a API de transcrição: {e}")
        return None

def generate_prompt(transcription_text, audio_duration):
    """Gera o prompt para identificar um único trecho impactante."""
    duration_str = f"{audio_duration:.2f}"  # Formata a duração como string
    prompt = os.getenv("OLLAMA_PROMPT_FIRST", "").replace("TRANSCRIBE", transcription_text)
    prompt = prompt.replace("DURATION", duration_str)  # Adiciona a duração ao prompt
    return prompt

def request_ollama(transcription_text, prompt):
    """Solicita ao Ollama o trecho a ser processado."""
    OLLAMA_HOSTNAME = os.getenv("OLLAMA_HOSTNAME")
    OLLAMA_PORT = os.getenv("OLLAMA_PORT")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

    url = f"http://{OLLAMA_HOSTNAME}:{OLLAMA_PORT}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "prompt": prompt
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        response_data = response.json()

        ollama_response = response_data.get("response", "").strip()
        if not ollama_response:
            logger.error(f"Ollama não retornou uma resposta válida. Resposta: {response_data}")
            return None

        logger.info(f"Resposta do Ollama: {ollama_response}")
        return ollama_response
    except requests.RequestException as e:
        logger.error(f"Erro na solicitação para Ollama: {str(e)}")
        return None


def classify_transcription(transcription_text, categories):
    """Classifica a transcrição usando o Ollama."""
    try:
        logger.info("Iniciando a identificação da categoria.")
        prompt = generate_category_prompt(transcription_text, categories)
        response = request_ollama(transcription_text, prompt)  # Reutiliza a função existente para chamar o Ollama
        if response:
            category = response.strip().lower()  # Normaliza a resposta para minúsculas
            normalized_categories = [cat.lower() for cat in categories]  # Normaliza categorias
            if category in normalized_categories:
                logger.info(f"Categoria identificada: {category}")
                return category
            else:
                logger.warning(f"Categoria retornada inválida: {category}. Categorias válidas: {categories}")
                return None
        return None
    except Exception as e:
        logger.error(f"Erro ao classificar transcrição: {e}")
        return None

def generate_category_prompt(transcription_text, categories):
    """Gera o prompt para classificação com base na lista de categorias."""
    categories_str = ", ".join(categories)  # Concatena as categorias
    prompt = CATEGORY_PROMPT.replace("CATEGORIES", categories_str).replace("TRANSCRIBE", transcription_text)
    return prompt

def get_categories_from_env():
    """Carrega a lista de categorias da variável de ambiente."""
    categories_str = os.getenv("CATEGORIES", "food,comedy,gamer,religion")  # Categorias padrão
    categories = [cat.strip() for cat in categories_str.split(",") if cat.strip()]  # Remove espaços extras
    return categories

def time_to_seconds(time_str):
    """Converte uma string de tempo no formato HH:MM:SS, MM:SS ou segundos em segundos."""
    try:
        time_str = time_str.strip().replace(',', '.').rstrip('.')
        parts = list(map(float, time_str.split(":")))

        if len(parts) == 1:
            return int(parts[0])
        elif len(parts) == 2:
            minutes, seconds = parts
            return int(minutes * 60 + seconds)
        elif len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours * 3600 + minutes * 60 + seconds)
        else:
            logger.error(f"Formato de tempo inválido: {time_str}")
            return None
    except ValueError as e:
        logger.error(f"Erro ao converter tempo '{time_str}' para segundos: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao converter tempo '{time_str}' para segundos: {e}")
        return None
