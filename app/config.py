import os

WORK_DIR = "/app/audiocast/"
AUTO_EDITOR_MARGIN = os.getenv("AUTO_EDITOR_MARGIN", "0.04sec")
PROCESS_TIMEOUT_SECONDS = int(os.getenv("PROCESS_TIMEOUT_SECONDS", "300"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
