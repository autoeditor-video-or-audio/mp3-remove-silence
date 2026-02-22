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

    Two-step pipeline for all input formats:
      1. auto-editor removes silence, outputting WAV (lossless intermediate)
      2. ffmpeg encodes the WAV to MP3 at 320kbps/48kHz (single lossy encode)

    This avoids an auto-editor 29.x bug where it ignores the -b:a flag
    (producing 64kbps instead of 320kbps) and cannot convert between formats
    (e.g. WAV to MP3 fails with 'Could not open encoder unknown').
    """
    margin = margin or AUTO_EDITOR_MARGIN
    wav_temp = input_path + ".silence_removed.wav"

    # Step 1: auto-editor removes silence -> WAV (lossless)
    ae_result = subprocess.run(
        [
            "auto-editor",
            input_path,
            "--margin", margin,
            "-o", wav_temp,
        ],
        capture_output=True,
        text=True,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )

    if ae_result.returncode != 0:
        logger.error(
            "auto-editor failed (rc=%d): stdout=%s stderr=%s",
            ae_result.returncode, ae_result.stdout, ae_result.stderr,
        )
        _remove_if_exists(wav_temp)
        raise RuntimeError(
            f"auto-editor exited with code {ae_result.returncode}: {ae_result.stderr}"
        )

    logger.info("auto-editor silence removal done: %s", wav_temp)

    # Step 2: ffmpeg encodes WAV -> MP3 at 320kbps/48kHz
    try:
        ffmpeg_result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", wav_temp,
                "-codec:a", AUDIO_CODEC,
                "-b:a", AUDIO_BITRATE,
                "-ar", AUDIO_SAMPLE_RATE,
                output_mp3_path,
            ],
            capture_output=True,
            text=True,
            timeout=PROCESS_TIMEOUT_SECONDS,
        )

        if ffmpeg_result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg encoding failed (rc={ffmpeg_result.returncode}): {ffmpeg_result.stderr}"
            )

        logger.info("MP3 encoding done: %s (320kbps, 48kHz)", output_mp3_path)
    finally:
        _remove_if_exists(wav_temp)


def _remove_if_exists(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
