from PIL import Image
from pathlib import Path
import argparse

def save_tile(image, path, quality):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "WEBP", quality=quality, method=6)

def build_tiles(source, destination, x, y, quality):
    with Image.open(source) as original:
        image = original.convert("RGB")

    if image.size != (4096, 4096):
        raise ValueError(
            f"Expected 4096 x 4096 pixels, got {image.size}"
        )

    destination = Path(destination)
    prefix = f"x{x}_y{y}"

    # Level A: one 1024 x 1024 tile
    small = image.resize((1024, 1024), Image.Resampling.LANCZOS)
    save_tile(small, destination / f"{prefix}_a.webp", quality)

    # Level B: four 1024 x 1024 tiles
    medium = image.resize((2048, 2048), Image.Resampling.LANCZOS)
    for row in range(2):
        for col in range(2):
            number = row * 2 + col + 1
            tile = medium.crop((
                col * 1024, row * 1024,
                (col + 1) * 1024, (row + 1) * 1024
            ))
            save_tile(
                tile,
                destination / f"{prefix}_b{number:02d}.webp",
                quality
            )

    # Level C: sixteen 1024 x 1024 tiles
    for row in range(4):
        for col in range(4):
            number = row * 4 + col + 1
            tile = image.crop((
                col * 1024, row * 1024,
                (col + 1) * 1024, (row + 1) * 1024
            ))
            save_tile(
                tile,
                destination / f"{prefix}_c{number:02d}.webp",
                quality
            )

    print(f"Success: 21 tiles generated in {destination}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--x", type=int, default=0)
    parser.add_argument("--y", type=int, default=0)
    parser.add_argument("--quality", type=int, default=90)
    args = parser.parse_args()

    build_tiles(
        args.source,
        args.destination,
        args.x,
        args.y,
        args.quality
    )
