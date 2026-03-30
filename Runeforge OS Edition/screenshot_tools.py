"""Screenshot and OCR extraction tool.

Requires: pillow, pytesseract
"""

import argparse
import datetime
import json
from pathlib import Path

from PIL import ImageGrab
import pytesseract


def capture_screen(output_dir: Path | None = None) -> dict[str, str]:
    target_dir = output_dir or Path.cwd()
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    out_path = target_dir / filename

    img = ImageGrab.grab()
    img.save(out_path)

    return {"screenshot_path": str(out_path.resolve())}


def capture_screen_with_ocr(output_dir: Path | None = None) -> dict[str, str]:
    base = capture_screen(output_dir)
    img = ImageGrab.grab()
    try:
        text = pytesseract.image_to_string(img)
    except Exception as ex:
        text = f"[OCR error: {ex}]"

    base["ocr_text"] = text
    return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ocr", action="store_true", help="Include OCR text in output")
    parser.add_argument("--output-dir", type=str, default=".", help="Directory for screenshots")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    payload = capture_screen_with_ocr(output_dir) if args.ocr else capture_screen(output_dir)
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
