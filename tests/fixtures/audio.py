"""Real WAV audio generation for tests.

Generates programmatically valid WAV files with actual PCM audio content —
not null bytes. The WAV header, channel count, sample rate, bit depth, and
data chunk length are all correct per the RIFF/WAV specification.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def generate_sine_wav(
    path: Path,
    duration_seconds: float = 1.0,
    frequency_hz: float = 440.0,
    sample_rate: int = 16000,
    amplitude: float = 0.5,
) -> Path:
    """Write a mono 16-bit 16kHz WAV file containing a sine wave.

    Args:
        path: Destination file path.
        duration_seconds: Length of audio in seconds.
        frequency_hz: Sine wave frequency (440 Hz = A4 note).
        sample_rate: Samples per second (16000 is standard for speech).
        amplitude: Peak amplitude as fraction of max (0.0–1.0).

    Returns:
        The path that was written.
    """
    n_samples = int(duration_seconds * sample_rate)
    peak = int(32767 * amplitude)

    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)   # mono
        wav.setsampwidth(2)   # 16-bit
        wav.setframerate(sample_rate)

        samples = [
            int(peak * math.sin(2 * math.pi * frequency_hz * i / sample_rate))
            for i in range(n_samples)
        ]
        wav.writeframes(struct.pack(f"<{n_samples}h", *samples))

    return path


def generate_silence_wav(
    path: Path,
    duration_seconds: float = 1.0,
    sample_rate: int = 16000,
) -> Path:
    """Write a mono 16-bit 16kHz WAV file containing silence.

    Unlike b'\\x00' * N, this writes a fully spec-compliant RIFF/WAV file
    with correct headers. The audio data happens to be silent (all zeros),
    but the file is a valid WAV that any parser can open without error.
    """
    n_samples = int(duration_seconds * sample_rate)

    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack(f"<{n_samples}h", *([0] * n_samples)))

    return path


def validate_wav(path: Path) -> dict:
    """Open and validate a WAV file, returning its properties.

    Raises:
        wave.Error: if the file is not a valid WAV.
    """
    with wave.open(str(path), "r") as wav:
        return {
            "channels":    wav.getnchannels(),
            "sample_width": wav.getsampwidth(),
            "frame_rate":  wav.getframerate(),
            "n_frames":    wav.getnframes(),
            "duration_s":  wav.getnframes() / wav.getframerate(),
        }
