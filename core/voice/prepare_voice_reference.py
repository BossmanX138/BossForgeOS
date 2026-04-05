import argparse
import wave
from pathlib import Path

import numpy as np


def _to_mono_float(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    if np.issubdtype(audio.dtype, np.integer):
        max_val = np.iinfo(audio.dtype).max
        audio = audio.astype(np.float32) / max(max_val, 1)
    else:
        audio = audio.astype(np.float32)
    return np.clip(audio, -1.0, 1.0)


def _read_wav(path: Path) -> tuple[int, np.ndarray]:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        frames = wf.getnframes()
        raw = wf.readframes(frames)

    if sampwidth == 1:
        audio = np.frombuffer(raw, dtype=np.uint8).astype(np.int16) - 128
    elif sampwidth == 2:
        audio = np.frombuffer(raw, dtype=np.int16)
    elif sampwidth == 4:
        audio = np.frombuffer(raw, dtype=np.int32)
    else:
        raise ValueError(f"unsupported sample width: {sampwidth}")

    if channels > 1:
        audio = audio.reshape(-1, channels)

    return sample_rate, audio


def _write_wav(path: Path, sample_rate: int, pcm_i16: np.ndarray) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_i16.tobytes())


def _moving_rms(audio: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if len(audio) < frame:
        return np.array([], dtype=np.float32)
    out = []
    for i in range(0, len(audio) - frame + 1, hop):
        chunk = audio[i : i + frame]
        out.append(float(np.sqrt(np.mean(chunk * chunk) + 1e-12)))
    return np.array(out, dtype=np.float32)


def _choose_segment(audio: np.ndarray, sr: int, seconds: float) -> np.ndarray:
    target = int(max(2.0, seconds) * sr)
    target = min(target, len(audio))
    if target <= 0:
        return audio

    frame = max(1, int(0.03 * sr))
    hop = max(1, int(0.01 * sr))
    rms = _moving_rms(audio, frame=frame, hop=hop)
    if rms.size == 0:
        return audio[:target]

    # Use voiced windows only and favor stable loud speech.
    threshold = max(float(np.percentile(rms, 55)), 0.015)
    voiced = np.where(rms >= threshold)[0]

    if voiced.size == 0:
        start = int(max(0, (len(audio) - target) // 2))
        return audio[start : start + target]

    # Longest contiguous voiced run.
    best_start = voiced[0]
    best_end = voiced[0]
    cur_start = voiced[0]
    cur_end = voiced[0]

    for idx in voiced[1:]:
        if idx == cur_end + 1:
            cur_end = idx
            continue
        if (cur_end - cur_start) > (best_end - best_start):
            best_start, best_end = cur_start, cur_end
        cur_start = idx
        cur_end = idx

    if (cur_end - cur_start) > (best_end - best_start):
        best_start, best_end = cur_start, cur_end

    region_start = best_start * hop
    region_end = min(len(audio), best_end * hop + frame)

    if region_end <= region_start:
        center = len(audio) // 2
    else:
        center = (region_start + region_end) // 2

    start = max(0, center - target // 2)
    end = start + target
    if end > len(audio):
        end = len(audio)
        start = max(0, end - target)

    segment = audio[start:end]

    # Light peak normalization.
    peak = float(np.max(np.abs(segment))) if segment.size else 0.0
    if peak > 1e-6:
        segment = segment * min(0.95 / peak, 1.8)

    return np.clip(segment, -1.0, 1.0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a clean voice reference clip for XTTS.")
    parser.add_argument("--input", required=True, help="Path to source wav")
    parser.add_argument("--output", required=True, help="Path to output wav")
    parser.add_argument("--seconds", type=float, default=10.0, help="Target reference length in seconds")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    sr, audio = _read_wav(input_path)
    mono = _to_mono_float(audio)
    segment = _choose_segment(mono, sr=sr, seconds=args.seconds)

    out_i16 = np.int16(np.clip(segment, -1.0, 1.0) * 32767)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_wav(output_path, sr, out_i16)

    print({
        "ok": True,
        "input": str(input_path),
        "output": str(output_path),
        "sample_rate": sr,
        "seconds": round(len(out_i16) / float(sr), 2),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
