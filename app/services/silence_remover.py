import logging
import subprocess
from pathlib import Path

from app.config import AUTO_EDITOR_MARGIN, PROCESS_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Audio quality: 320k bitrate (max MP3), libmp3lame, 48kHz sample rate
AUDIO_CODEC = "libmp3lame"
AUDIO_BITRATE = "320k"
AUDIO_SAMPLE_RATE = "48000"


def remove_silence(input_path: str, output_mp3_path: str, margin: str = None) -> None:
    """Run auto-editor to remove silence, outputting directly to MP3.

    Uses libmp3lame codec with 320k bitrate (maximum MP3 quality) and
    48kHz sample rate in a single transcode step.
    """
    margin = margin or AUTO_EDITOR_MARGIN

    result = subprocess.run(
        [
            "auto-editor",
            input_path,
            "--margin", margin,
            "-c:a", AUDIO_CODEC,
            "-b:a", AUDIO_BITRATE,
            "-ar", AUDIO_SAMPLE_RATE,
            "-o", output_mp3_path,
        ],
        capture_output=True,
        text=True,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )

    if result.returncode != 0:
        logger.error(
            "auto-editor failed (rc=%d): stdout=%s stderr=%s",
            result.returncode,
            result.stdout,
            result.stderr,
        )
        raise RuntimeError(
            f"auto-editor exited with code {result.returncode}: {result.stderr}"
        )

    logger.info("auto-editor finished: %s", output_mp3_path)
