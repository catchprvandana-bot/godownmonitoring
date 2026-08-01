"""Generate a synthetic crop-spoilage image dataset for local training.

Creates:
    ml/dataset/
        train/<class>/  (300 images each)
        val/<class>/    (75 images each)

Each 224×224 JPEG has class-specific colour/texture patterns so MobileNetV2
has real signal to learn — not just noise. Takes ~30 seconds on CPU.

Healthy images now look like realistic grains (rice, wheat, maize, millet,
sorghum) rendered as close-up macro shots of grain kernels on a surface.

Usage (from project root):
    python ml/generate_synthetic_dataset.py
    python ml/generate_synthetic_dataset.py --regen-healthy   # replace healthy only
"""

import argparse
import math
import os
import random
from pathlib import Path

import numpy as np  # pyright: ignore[reportMissingImports]
from PIL import Image, ImageDraw, ImageFilter  # pyright: ignore[reportMissingImports]

# ---------------------------------------------------------------------------
# Grain type definitions for the "healthy" class
# Each entry defines the visual appearance of one grain species.
# ---------------------------------------------------------------------------
GRAIN_TYPES = [
    {
        "name": "rice",
        "bg": (210, 195, 160),          # pale beige surface
        "kernel_color": (240, 228, 196), # creamy white rice grain
        "kernel_shape": "elongated",     # long thin oval
        "kernel_w": (6, 10),
        "kernel_h": (18, 30),
        "kernel_count": (60, 100),
        "sheen": True,
    },
    {
        "name": "wheat",
        "bg": (185, 148, 90),            # golden-brown surface
        "kernel_color": (210, 170, 100), # amber wheat kernel
        "kernel_shape": "oval",
        "kernel_w": (10, 16),
        "kernel_h": (14, 20),
        "kernel_count": (40, 70),
        "sheen": False,
    },
    {
        "name": "maize",
        "bg": (195, 155, 60),            # corn-yellow surface
        "kernel_color": (240, 200, 60),  # bright yellow corn kernel
        "kernel_shape": "rounded",
        "kernel_w": (14, 22),
        "kernel_h": (12, 18),
        "kernel_count": (25, 45),
        "sheen": True,
    },
    {
        "name": "millet",
        "bg": (200, 175, 120),           # light tan surface
        "kernel_color": (230, 205, 150), # pale golden millet
        "kernel_shape": "round",
        "kernel_w": (5, 8),
        "kernel_h": (5, 8),
        "kernel_count": (80, 140),
        "sheen": False,
    },
    {
        "name": "sorghum",
        "bg": (160, 110, 70),            # reddish-brown surface
        "kernel_color": (195, 140, 95),  # dark reddish sorghum
        "kernel_shape": "round",
        "kernel_w": (9, 13),
        "kernel_h": (9, 13),
        "kernel_count": (45, 75),
        "sheen": False,
    },
]

CLASS_CONFIGS = {
    "healthy": {
        "texture": "grain",             # special grain rendering
        "noise_scale": 10,
    },
    "mold": {
        "bg_color": (80, 60, 30),         # dark brown base
        "spot_color": (180, 180, 50),     # yellowish mold spots
        "noise_scale": 30,
        "spots": 20,
        "texture": "fuzzy",
    },
    "pest_damage": {
        "bg_color": (139, 90, 43),        # tan/brown base
        "spot_color": (30, 20, 10),       # dark damage holes
        "noise_scale": 20,
        "spots": 12,
        "texture": "holed",
    },
    "discoloration": {
        "bg_color": (180, 150, 60),       # yellowish base
        "spot_color": (200, 100, 40),     # orange/red patches
        "noise_scale": 25,
        "spots": 8,
        "texture": "blotchy",
    },
}

IMG_SIZE = (224, 224)


def _random_variation(color: tuple[int, int, int], var: int = 25) -> tuple[int, int, int]:
    """Add small random variation to an RGB colour tuple."""
    return tuple(
        max(0, min(255, c + random.randint(-var, var))) for c in color
    )  # type: ignore[return-value]


def _draw_grain_kernel(
    img: Image.Image,
    rng: random.Random,
    cx: int,
    cy: int,
    w: int,
    h: int,
    angle_deg: float,
    color: tuple[int, int, int],
    shape: str,
    sheen: bool,
) -> None:
    """Draw a single grain kernel as a rotated ellipse with optional sheen."""
    pad = max(w, h) + 6
    tmp = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)

    # Kernel body — solid fill
    dark_edge = tuple(max(0, c - 30) for c in color)  # type: ignore[misc]
    if shape == "elongated":
        # Outer shadow ring
        d.ellipse([pad - w - 1, pad - h - 1, pad + w + 1, pad + h + 1], fill=(*dark_edge, 220))
        # Kernel body
        d.ellipse([pad - w, pad - h, pad + w, pad + h], fill=(*color, 255))
        # Centre ridge highlight
        hlt = tuple(min(255, c + 50) for c in color)  # type: ignore[misc]
        d.ellipse([pad - w // 3, pad - h + 5, pad + w // 3, pad + h - 5], fill=(*hlt, 230))
    elif shape in ("oval", "rounded"):
        d.ellipse([pad - w - 1, pad - h // 2 - 1, pad + w + 1, pad + h // 2 + 1], fill=(*dark_edge, 220))
        d.ellipse([pad - w, pad - h // 2, pad + w, pad + h // 2], fill=(*color, 255))
        hlt = tuple(min(255, c + 45) for c in color)  # type: ignore[misc]
        d.ellipse([pad - w + 3, pad - h // 2 + 3, pad + w // 2, pad], fill=(*hlt, 200))
    else:  # round — millet / sorghum
        d.ellipse([pad - w - 1, pad - h - 1, pad + w + 1, pad + h + 1], fill=(*dark_edge, 220))
        d.ellipse([pad - w, pad - h, pad + w, pad + h], fill=(*color, 255))
        hlt = tuple(min(255, c + 45) for c in color)  # type: ignore[misc]
        d.ellipse([pad - w + 2, pad - h + 2, pad, pad], fill=(*hlt, 190))

    # Sheen highlight (glossy grain surface)
    if sheen:
        sheen_col = tuple(min(255, c + 80) for c in color)  # type: ignore[misc]
        if shape == "elongated":
            d.ellipse([pad - w + 2, pad - h + 3, pad - 2, pad - h // 2], fill=(*sheen_col, 180))
        else:
            d.ellipse([pad - w + 2, pad - h + 2, pad - 2, pad], fill=(*sheen_col, 160))

    # Rotate and paste onto main canvas using the alpha channel as mask
    rotated = tmp.rotate(angle_deg, resample=Image.BICUBIC, expand=False)
    img.paste(rotated, (cx - pad, cy - pad), rotated)


def _make_grain_image(rng: random.Random) -> Image.Image:
    """Create a 224×224 image that looks like a close-up of grain kernels."""
    # Pick a random grain type
    gtype = rng.choice(GRAIN_TYPES)

    # Background: slightly textured surface colour
    bg_base = _random_variation(gtype["bg"], 15)
    arr = np.full((224, 224, 3), bg_base, dtype=np.uint8)
    # Add fine noise to background
    noise = np.random.randint(-8, 9, arr.shape).astype(np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    img = Image.fromarray(arr, "RGB").convert("RGBA")

    n_kernels = rng.randint(*gtype["kernel_count"])
    shape = gtype["kernel_shape"]

    for _ in range(n_kernels):
        cx = rng.randint(5, 219)
        cy = rng.randint(5, 219)
        w = rng.randint(*gtype["kernel_w"])
        h = rng.randint(*gtype["kernel_h"])
        angle = rng.uniform(0, 180)

        # Per-kernel colour variation
        kc = _random_variation(gtype["kernel_color"], 18)

        _draw_grain_kernel(img, rng, cx, cy, w, h, angle, kc, shape, gtype["sheen"])

    # Convert back to RGB
    img = img.convert("RGB")

    # Light blur for photorealistic softness
    img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 0.9)))

    # Add very light overall noise for texture grain
    arr2 = np.array(img).astype(np.int16)
    arr2 = np.clip(arr2 + np.random.randint(-6, 7, arr2.shape), 0, 255).astype(np.uint8)
    img = Image.fromarray(arr2, "RGB")

    return img


def _make_image(class_name: str, rng: random.Random) -> Image.Image:
    """Dispatch to grain renderer (healthy) or legacy textured renderer."""
    if class_name == "healthy":
        return _make_grain_image(rng)

    cfg = CLASS_CONFIGS[class_name]
    bg = _random_variation(cfg["bg_color"], 20)
    arr = np.full((224, 224, 3), bg, dtype=np.uint8)

    # Add Gaussian noise
    noise = rng.randint(cfg["noise_scale"] // 2, cfg["noise_scale"])
    arr = np.clip(arr.astype(np.int16) + np.random.randint(-noise, noise + 1, arr.shape), 0, 255).astype(np.uint8)

    img = Image.fromarray(arr, "RGB")
    draw = ImageDraw.Draw(img)

    texture = cfg["texture"]

    if texture == "fuzzy":
        # Mold: irregular circular blobs
        for _ in range(cfg["spots"]):
            x, y = rng.randint(10, 214), rng.randint(10, 214)
            r = rng.randint(6, 22)
            col = _random_variation(cfg["spot_color"], 30)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=col)
        img = img.filter(ImageFilter.GaussianBlur(radius=1.5))

    elif texture == "holed":
        # Pest damage: dark irregular holes + ragged edges
        for _ in range(cfg["spots"]):
            x, y = rng.randint(15, 209), rng.randint(15, 209)
            rx, ry = rng.randint(4, 14), rng.randint(4, 10)
            col = _random_variation(cfg["spot_color"], 10)
            draw.ellipse([x - rx, y - ry, x + rx, y + ry], fill=col)

    elif texture == "blotchy":
        # Discoloration: large uneven patches
        for _ in range(cfg["spots"]):
            x, y = rng.randint(0, 200), rng.randint(0, 200)
            w, h = rng.randint(20, 60), rng.randint(20, 50)
            col = _random_variation(cfg["spot_color"], 35)
            draw.rectangle([x, y, x + w, y + h], fill=col)
        img = img.filter(ImageFilter.SMOOTH)

    # Final slight blur to look more natural
    if texture != "holed":
        img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0, 0.8)))

    return img


def generate(
    output_dir: Path,
    train_count: int = 300,
    val_count: int = 75,
    seed: int = 42,
    regen_healthy: bool = False,
):
    rng = random.Random(seed)
    np.random.seed(seed)

    for split, count in [("train", train_count), ("val", val_count)]:
        for class_name in CLASS_CONFIGS:
            folder = output_dir / split / class_name
            folder.mkdir(parents=True, exist_ok=True)

            # When --regen-healthy is set, wipe existing healthy images first
            if regen_healthy and class_name == "healthy":
                existing_files = list(folder.glob("*.jpg"))
                for f in existing_files:
                    f.unlink()
                print(f"  {split}/{class_name}: deleted {len(existing_files)} old images")
                existing = 0
            else:
                existing = len(list(folder.glob("*.jpg")))

            needed = count - existing
            if needed <= 0:
                print(f"  {split}/{class_name}: already has {existing} images, skipping")
                continue

            print(f"  Generating {needed} images -> {split}/{class_name}/")
            for i in range(needed):
                img = _make_image(class_name, rng)
                img.save(folder / f"{class_name}_{existing + i:04d}.jpg", quality=85)

    print("\n[DONE] Dataset ready!")
    for split in ["train", "val"]:
        counts = {cls: len(list((output_dir / split / cls).glob("*.jpg"))) for cls in CLASS_CONFIGS}
        print(f"  {split}: " + ", ".join(f"{cls}={n}" for cls, n in counts.items()))


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic spoilage dataset")
    parser.add_argument("--output", default=str(Path(__file__).parent / "dataset"), help="Output directory")
    parser.add_argument("--train", type=int, default=300, help="Images per class in train split")
    parser.add_argument("--val", type=int, default=75, help="Images per class in val split")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--regen-healthy",
        action="store_true",
        help="Delete and regenerate all healthy images (grain textures)",
    )
    args = parser.parse_args()

    out = Path(args.output)
    print(f"[*] Generating synthetic dataset in: {out.resolve()}")
    generate(out, train_count=args.train, val_count=args.val, seed=args.seed, regen_healthy=args.regen_healthy)


if __name__ == "__main__":
    main()
