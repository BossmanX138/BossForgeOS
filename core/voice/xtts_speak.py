import argparse
import json
import wave
from pathlib import Path

import numpy as np


def _resolve_path(value: str, root: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _apply_playback_rate(output_path: Path, rate: float) -> None:
    if abs(rate - 1.0) < 1e-3:
        return
    if rate <= 0:
        return

    with wave.open(str(output_path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if sampwidth != 2:
        return

    audio = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels)

    frames = audio.shape[0]
    if frames < 2:
        return

    new_frames = max(1, int(frames / rate))
    src = np.linspace(0.0, frames - 1, num=frames, dtype=np.float64)
    dst = np.linspace(0.0, frames - 1, num=new_frames, dtype=np.float64)

    if channels > 1:
        out = np.zeros((new_frames, channels), dtype=np.int16)
        for ch in range(channels):
            out[:, ch] = np.interp(dst, src, audio[:, ch]).astype(np.int16)
    else:
        out = np.interp(dst, src, audio).astype(np.int16)

    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        wf.writeframes(out.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate speech with XTTS profile")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--playback-rate", type=float, default=0.0)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    profile_path = _resolve_path(args.profile, repo_root)
    output_path = _resolve_path(args.output, repo_root)

    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    model_dir = _resolve_path(str(profile.get("xtts_model_dir", ".models/coqui--XTTS-v2")), repo_root)
    config_path = _resolve_path(str(profile.get("xtts_config", ".models/coqui--XTTS-v2/config.json")), repo_root)
    reference_wav = _resolve_path(str(profile.get("reference_wav", "voices/codemage/reference.wav")), repo_root)
    language = str(profile.get("language", "en"))
    playback_rate = float(profile.get("playback_rate", 1.0) or 1.0)
    if args.playback_rate and args.playback_rate > 0:
        playback_rate = float(args.playback_rate)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    from TTS.api import TTS  # Imported lazily so only XTTS env needs this dependency.

    tts = TTS(model_path=str(model_dir), config_path=str(config_path), progress_bar=False, gpu=False)
    tts.tts_to_file(
        text=args.text,
        speaker_wav=str(reference_wav),
        language=language,
        file_path=str(output_path),
    )
    _apply_playback_rate(output_path=output_path, rate=playback_rate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
