"""Decode a real audio file through faster-whisper with the installed PyAV.

Other tests replace the engine, so a PyAV release that breaks faster-whisper's
decoder (PyAV 19 dropped av.open(metadata_errors=...)) went unnoticed and every
transcription in the 0.7.0 builds failed. This runs the actual decode path.
"""

import wave

from faster_whisper.audio import decode_audio


def test_decode_audio_reads_a_wav_file(tmp_path):
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 1600)  # 0.1 s of silence

    audio = decode_audio(str(path), sampling_rate=16000)

    assert len(audio) == 1600
