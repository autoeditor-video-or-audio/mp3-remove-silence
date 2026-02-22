# MP3 Remove Silence

Microservice that removes silence segments from audio files using auto-editor. Accepts an audio file via multipart upload and returns the processed audio with silence removed as a binary response.

---

## Visao Geral

The **MP3 Remove Silence** service is a single-purpose microservice in the Edit Audio to Movie platform. It wraps the `auto-editor` CLI tool behind a FastAPI endpoint, providing:

- **Silence detection and removal** via auto-editor's audio analysis
- **Configurable margin** -- control how aggressively silence is trimmed
- **High-quality output** -- MP3 encoded at 320kbps, 48kHz using libmp3lame
- **Health validation** -- verifies that the auto-editor binary is available at startup

This service is called by the Backend REST API during Step 1 of the processing pipeline. It does not manage jobs or state -- it receives a file, processes it, and returns the result synchronously.

### Key Characteristics

- **Stateless** -- no database, no job tracking, no persistent storage
- **Synchronous processing** -- request blocks until audio processing completes
- **Binary response** -- returns the processed audio file directly in the HTTP response body
- **Configurable timeout** -- prevents runaway processes from consuming resources

---

## Quick Start

### Prerequisites

- Python 3.12+
- `auto-editor` CLI installed and available on PATH
- `ffmpeg` installed (required by auto-editor)

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Verify auto-editor is available
auto-editor --help

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8001

# Or with Docker
docker compose up mp3-remove-silence -d --build
```

### Verify

```bash
curl http://localhost:8001/health
# {"status":"ok","auto_editor_path":"/usr/local/bin/auto-editor"}
```

### Remove Silence from a File

```bash
curl -X POST http://localhost:8001/api/v1/audio/remove-silence \
  -F "file=@episode.mp3" \
  -o processed.mp3

# With custom margin
curl -X POST http://localhost:8001/api/v1/audio/remove-silence \
  -F "file=@episode.mp3" \
  -F "margin=0.06" \
  -o processed.mp3
```

---

## Arquitetura

```
                  Backend REST API (:8000)
                          |
                    POST /api/v1/audio/remove-silence
                    (multipart: file + optional margin)
                          |
                          v
         +------------------------------------+
         |   MP3 Remove Silence (:8001)       |
         |                                    |
         |  1. Save uploaded file to WORK_DIR |
         |  2. Run auto-editor CLI            |
         |  3. Read processed output          |
         |  4. Return binary response         |
         |  5. Clean up temp files            |
         +------------------------------------+
                          |
                    uses externally
                          |
                          v
                  +----------------+
                  |  auto-editor   |
                  |  CLI binary    |
                  |  (+ ffmpeg)    |
                  +----------------+
```

### Processing Flow

```
  Input File          auto-editor                   Output
  ----------    ----------------------    -------------------------
  .mp3/.wav  -> silence detection     ->  MP3 (libmp3lame, 320kbps,
  .m4a/.flac    margin-based trimming      48kHz) returned as binary
  .ogg/.aac     ffmpeg re-encoding         HTTP response
  .mpeg
```

1. Client sends audio file as multipart form data
2. Service saves the file to `WORK_DIR` with a unique filename
3. `auto-editor` CLI is invoked with the configured margin parameter
4. auto-editor analyzes audio levels, identifies silence segments, and removes them
5. The processed file is encoded as MP3 (libmp3lame, 320kbps, 48kHz)
6. Service reads the output file and returns it as a binary HTTP response
7. Temporary files in `WORK_DIR` are cleaned up

---

## API Endpoints

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check with auto-editor binary validation |

**Response (200):**
```json
{
  "status": "ok",
  "auto_editor_path": "/usr/local/bin/auto-editor"
}
```

### Silence Removal

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/audio/remove-silence` | Remove silence from an audio file |

**Request:**
```
Content-Type: multipart/form-data
file:   <audio file>    (required)
margin: 0.04            (optional, default from AUTO_EDITOR_MARGIN env)
```

**Supported extensions:** `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.aac`, `.mpeg`

**Response (200):**
```
Content-Type: audio/mpeg
Body: <binary audio data>
```

The `margin` parameter controls the silence detection threshold. Lower values remove more silence; higher values preserve more of the original audio around speech boundaries.

### Output Specification

| Property | Value |
|----------|-------|
| Format | MP3 |
| Codec | libmp3lame |
| Bitrate | 320 kbps |
| Sample Rate | 48,000 Hz |

---

## Configuracao

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8001` | Server port |
| `WORK_DIR` | `/app/audiocast/` | Temporary directory for processing files |
| `AUTO_EDITOR_MARGIN` | `0.04sec` | Default silence margin for auto-editor |
| `PROCESS_TIMEOUT_SECONDS` | `300` | Maximum processing time before timeout (seconds) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Margin Parameter

The margin controls how much silence auto-editor preserves around detected speech:

| Value | Effect |
|-------|--------|
| `0.02sec` | Aggressive -- removes nearly all silence |
| `0.04sec` | Default -- balanced silence removal |
| `0.06sec` | Conservative -- preserves natural pauses |
| `0.10sec` | Minimal -- only removes long silence gaps |

---

## Desenvolvimento

### Project Structure

```
mp3-remove-silence/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── audio.py              # Silence removal endpoint
│   │       └── health.py             # Health check with binary validation
│   ├── core/
│   │   └── config.py                 # Settings from environment variables
│   ├── services/
│   │   └── silence_remover.py        # auto-editor CLI wrapper
│   ├── utils/
│   │   ├── binary_check.py           # Verify auto-editor binary exists
│   │   └── logging.py                # Logging configuration
│   └── main.py                       # FastAPI application entry point
├── Dockerfile
├── requirements.txt
└── README.md
```

### Running Locally (Development)

```bash
# Create virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Ensure auto-editor and ffmpeg are installed
pip install auto-editor
# ffmpeg must be installed separately (e.g., apt install ffmpeg)

# Start with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Test with a sample file
curl -X POST http://localhost:8001/api/v1/audio/remove-silence \
  -F "file=@test.mp3" -o output.mp3
```

### Dependencies

The service requires two external binaries:

- **auto-editor** -- Python package that provides the CLI for silence detection and removal
- **ffmpeg** -- Used internally by auto-editor for audio decoding, encoding, and format conversion

Both must be available on the system PATH for the service to function correctly. The `/health` endpoint validates their presence at runtime.

---

## Stack Tecnologica

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | FastAPI | Async REST API framework |
| **Runtime** | Python 3.12 | Language runtime |
| **Silence Removal** | auto-editor CLI | Audio analysis and silence detection |
| **Audio Processing** | ffmpeg | Audio encoding and format conversion |
| **Server** | uvicorn | ASGI server |
| **Containerization** | Docker | Production deployment |

---

## License

Private project -- All rights reserved.
