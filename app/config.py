import os

WORK_DIR = "/app/audiocast/"
BUCKET_NAME = os.getenv("BUCKET_NAME", "audiocast")
NOSILENCE_PREFIX = os.getenv("NOSILENCE_PREFIX", "nosilence")
QUEUE_INPUT = os.getenv("QUEUE_INPUT", "00_audiocast")
QUEUE_OUTPUT = os.getenv("QUEUE_OUTPUT", "01_audiocast")
AUTO_EDITOR_MARGIN = os.getenv("AUTO_EDITOR_MARGIN", "0.04sec")
