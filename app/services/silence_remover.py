import logging
import subprocess
from pathlib import Path

from pydub import AudioSegment

from app.config import AUTO_EDITOR_MARGIN, PROCESS_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


def remove_silence(input_path: str, output_mp3_path: str, margin: str = None) -> None:
    """Run auto-editor to remove silence, then convert output to mp3 via pydub.

    auto-editor outputs a video container (.mp4) even for audio-only inputs.
    We re-encode the result back to .mp3 using pydub (wraps ffmpeg).
    """
    margin = margin or AUTO_EDITOR_MARGIN
    auto_editor_output = Path(input_path).with_suffix(".auto_editor_out.mp4")

    try:
        result = subprocess.run(
            [
                "auto-editor",
                input_path,
                "--margin",
                margin,
                "-o",
                str(auto_editor_output),
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

        logger.info("auto-editor finished, converting to mp3")

        audio = AudioSegment.from_file(str(auto_editor_output))
        audio.export(output_mp3_path, format="mp3")

        logger.info("MP3 conversion complete: %s", output_mp3_path)

    finally:
        if auto_editor_output.exists():
            auto_editor_output.unlink()
