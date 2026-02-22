import logging
import os
import shutil
import subprocess
import uuid

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from app.config import WORK_DIR
from app.logger_config import setup_logger
from app.services.silence_remover import remove_silence
from app.utils.file_utils import create_directory

setup_logger()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".mpeg"}

app = FastAPI(title="MP3 Remove Silence API")

create_directory(WORK_DIR)


@app.get("/health")
async def health():
    ae_path = shutil.which("auto-editor")
    if ae_path is None:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "auto-editor not found in PATH"},
        )
    return {"status": "ok", "auto_editor_path": ae_path}


@app.post("/api/v1/audio/remove-silence")
async def remove_silence_endpoint(
    file: UploadFile = File(...),
    margin: str = Form(default=None),
):
    if not file.filename:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "VALIDATION_ERROR", "message": "No filename provided"}},
        )

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Extension '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                }
            },
        )

    request_id = str(uuid.uuid4())
    input_path = os.path.join(WORK_DIR, f"{request_id}{ext}")
    output_path = os.path.join(WORK_DIR, f"{request_id}_processed.mp3")

    try:
        content = await file.read()
        if len(content) == 0:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "VALIDATION_ERROR", "message": "Uploaded file is empty"}},
            )

        with open(input_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.exception("Failed to save upload")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "UPLOAD_FAILED", "message": str(e)}},
        )

    try:
        remove_silence(input_path, output_path, margin=margin)
    except subprocess.TimeoutExpired:
        _cleanup_files(input_path, output_path)
        return JSONResponse(
            status_code=504,
            content={"error": {"code": "PROCESS_TIMEOUT", "message": "Processing timed out"}},
        )
    except Exception as e:
        logger.exception("Processing failed")
        _cleanup_files(input_path, output_path)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "PROCESS_FAILED", "message": f"Processing failed: {e}"}},
        )

    cleanup_task = BackgroundTask(_cleanup_files, input_path, output_path)
    return FileResponse(
        path=output_path,
        media_type="audio/mpeg",
        filename=file.filename,
        background=cleanup_task,
    )


def _cleanup_files(*paths):
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug("Cleaned up: %s", path)
        except Exception as e:
            logger.warning("Failed to clean up %s: %s", path, e)
