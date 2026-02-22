import logging
import os
import subprocess

from app.config import AUTO_EDITOR_MARGIN, PROCESS_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Audio quality: 320k bitrate (max MP3), libmp3lame, 48kHz sample rate
AUDIO_CODEC = "libmp3lame"
AUDIO_BITRATE = "320k"
AUDIO_SAMPLE_RATE = "48000"


def remove_silence(input_path: str, output_mp3_path: str, margin: str = None) -> None:
    """Run auto-editor to remove silence, outputting MP3 at 320kbps/48kHz.

    auto-editor 29.x cannot convert between audio formats (e.g. WAV to MP3),
    failing with 'Could not open encoder unknown'. For non-MP3 inputs, we
    pre-convert to MP3 via ffmpeg, then let auto-editor process MP3-to-MP3
    as normal. At 320kbps the quality loss is imperceptible for speech.
    """
    margin = margin or AUTO_EDITOR_MARGIN
    converted_path = None
    ext = os.path.splitext(input_path)[1].lower()

    if ext != ".mp3":
        converted_path = input_path + ".converted.mp3"
        logger.info("Converting %s to MP3 before processing", ext)
        _ffmpeg_encode(input_path, converted_path)
        ae_input = converted_path
    else:
        ae_input = input_path

    try:
        result = subprocess.run(
            [
                "auto-editor",
                ae_input,
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
                result.returncode, result.stdout, result.stderr,
            )
            raise RuntimeError(
                f"auto-editor exited with code {result.returncode}: {result.stderr}"
            )

        logger.info("auto-editor finished: %s", output_mp3_path)
    finally:
        _remove_if_exists(converted_path)


def _ffmpeg_encode(input_path: str, output_path: str) -> None:
    """Encode audio to MP3 at 320kbps/48kHz using ffmpeg."""
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", input_path,
            "-codec:a", AUDIO_CODEC,
            "-b:a", AUDIO_BITRATE,
            "-ar", AUDIO_SAMPLE_RATE,
            output_path,
        ],
        capture_output=True,
        text=True,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg encoding failed (rc={result.returncode}): {result.stderr}"
        )
    logger.info("Encoded %s -> %s", input_path, output_path)


def _remove_if_exists(path: str) -> None:
    if path is None:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
