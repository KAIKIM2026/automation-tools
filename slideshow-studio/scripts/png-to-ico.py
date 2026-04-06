from pathlib import Path
import sys

from PIL import Image


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python png-to-ico.py <input_png> <output_ico>")

    input_path = Path(sys.argv[1]).resolve()
    output_path = Path(sys.argv[2]).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as image:
        image = image.convert("RGBA")
        image.save(
            output_path,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
