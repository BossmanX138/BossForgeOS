import argparse
import json
from pathlib import Path


def _resolve_path(value: str, root: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate speech with XTTS profile")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    profile_path = _resolve_path(args.profile, repo_root)
    output_path = _resolve_path(args.output, repo_root)

    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    model_dir = _resolve_path(str(profile.get("xtts_model_dir", ".models/coqui--XTTS-v2")), repo_root)
    config_path = _resolve_path(str(profile.get("xtts_config", ".models/coqui--XTTS-v2/config.json")), repo_root)
    reference_wav = _resolve_path(str(profile.get("reference_wav", "voices/codemage/reference.wav")), repo_root)
    language = str(profile.get("language", "en"))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    from TTS.api import TTS  # Imported lazily so only XTTS env needs this dependency.

    tts = TTS(model_path=str(model_dir), config_path=str(config_path), progress_bar=False, gpu=False)
    tts.tts_to_file(
        text=args.text,
        speaker_wav=str(reference_wav),
        language=language,
        file_path=str(output_path),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
