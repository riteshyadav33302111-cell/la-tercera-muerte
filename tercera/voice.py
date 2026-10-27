"""
Optional voice layer: offline speech-to-text (whisper.cpp) and
text-to-speech (Piper TTS) with reverb for the ghost's voice.

These features require external binaries. They are disabled by default.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .config import get_config

_cfg = get_config()
_voice_cfg = _cfg.get("voice", {})


def voice_enabled() -> bool:
    return _voice_cfg.get("enabled", False)


# ---------------------------------------------------------------------------
# Speech-to-text via whisper.cpp
# ---------------------------------------------------------------------------

def transcribe_from_mic(duration_seconds: int = 5) -> Optional[str]:
    """
    Record audio from mic and transcribe with whisper.cpp.
    Requires: whisper.cpp (whisper-cli or main binary), sox or ffmpeg.
    """
    if not voice_enabled():
        return None

    whisper_bin = shutil.which("whisper-cli") or shutil.which("whisper") or shutil.which("main")
    if not whisper_bin:
        print("[voice] whisper.cpp binary not found — skipping speech input")
        return None

    # Record audio
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        audio_file = f.name

    try:
        # Try sox
        sox = shutil.which("sox") or shutil.which("rec")
        if sox:
            subprocess.run(
                [sox, "-d", "-r", "16000", "-c", "1", audio_file,
                 "trim", "0", str(duration_seconds)],
                capture_output=True,
                timeout=duration_seconds + 5,
            )
        else:
            print("[voice] sox not found — cannot record audio")
            return None

        # Transcribe
        model = _voice_cfg.get("whisper_model", "base")
        model_path = Path.home() / ".local" / "share" / "whisper" / f"ggml-{model}.bin"

        result = subprocess.run(
            [whisper_bin, "-m", str(model_path), "-f", audio_file,
             "--output-txt", "--no-prints"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            # whisper.cpp outputs to <file>.txt
            txt_file = audio_file + ".txt"
            if Path(txt_file).exists():
                return Path(txt_file).read_text().strip()

    except Exception as e:
        print(f"[voice] Transcription error: {e}")
    finally:
        Path(audio_file).unlink(missing_ok=True)

    return None


# ---------------------------------------------------------------------------
# Text-to-speech via Piper TTS with reverb
# ---------------------------------------------------------------------------

def speak_ghost(text: str) -> None:
    """
    Speak text through Piper TTS with a ghostly reverb effect.
    Requires: piper, sox.
    """
    if not voice_enabled():
        return

    piper_bin = shutil.which("piper")
    sox_bin = shutil.which("play") or shutil.which("sox")

    if not piper_bin:
        print("[voice] piper not found — skipping TTS")
        return

    voice = _voice_cfg.get("piper_voice", "en_US-lessac-medium")
    voice_model = Path.home() / ".local" / "share" / "piper" / f"{voice}.onnx"

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        audio_file = f.name

    try:
        # Generate speech
        proc = subprocess.Popen(
            [piper_bin, "--model", str(voice_model),
             "--output_file", audio_file],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.communicate(input=text.encode(), timeout=30)

        if not Path(audio_file).exists():
            return

        # Apply reverb and pitch shift via sox
        apply_reverb = _voice_cfg.get("reverb", True)
        if sox_bin and apply_reverb:
            subprocess.run(
                [sox_bin, audio_file, "-d",
                 "pitch", "-200",      # Slightly lower pitch
                 "reverb", "80",       # Heavy reverb
                 "gain", "-3"],        # Reduce volume slightly
                timeout=30,
            )
        elif sox_bin:
            subprocess.run([sox_bin, audio_file, "-d"], timeout=30)

    except Exception as e:
        print(f"[voice] TTS error: {e}")
    finally:
        Path(audio_file).unlink(missing_ok=True)
