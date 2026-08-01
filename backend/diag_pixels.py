"""Diagnostic: dump pixel statistics for one image from each class."""
import colorsys, sys
from pathlib import Path
from PIL import Image
import io

PROJECT_ROOT = Path(__file__).resolve().parent.parent
dataset_dir = PROJECT_ROOT / "ml" / "dataset" / "val"

for cls in ["healthy", "mold", "pest_damage", "discoloration"]:
    cls_dir = dataset_dir / cls
    images = sorted(cls_dir.glob("*.jpg"))
    if not images:
        print(f"\n=== {cls} (no images found) ===")
        continue
    img_path = images[0]
    
    img = Image.open(str(img_path)).convert("RGB").resize((128, 128))
    pixels = list(img.getdata())
    total = len(pixels)
    
    very_dark = 0   # v < 0.14
    dark_018 = 0    # v < 0.18
    dark_022 = 0    # v < 0.22
    mold_spot = 0   # hue 48-95, s>=0.35, v>0.25
    mold_wide = 0   # hue 45-100, s>=0.25, v>0.20
    orange = 0      # hue<=24, s>=0.60, v>0.35
    orange_wide = 0 # hue<=30, s>=0.45, v>0.30
    b_sum = 0.0
    
    hue_hist = [0]*36  # 10-degree buckets
    
    for r, g, b in pixels:
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        hue_deg = h * 360
        b_sum += v
        
        bucket = min(int(hue_deg / 10), 35)
        hue_hist[bucket] += 1
        
        if v < 0.14: very_dark += 1
        if v < 0.18: dark_018 += 1
        if v < 0.22: dark_022 += 1
        
        if 48 <= hue_deg <= 95 and s >= 0.35 and v > 0.25: mold_spot += 1
        if 45 <= hue_deg <= 100 and s >= 0.25 and v > 0.20: mold_wide += 1
        if (hue_deg <= 24 or hue_deg >= 345) and s >= 0.60 and v > 0.35: orange += 1
        if (hue_deg <= 30 or hue_deg >= 340) and s >= 0.45 and v > 0.30: orange_wide += 1
    
    mean_b = b_sum / total
    print(f"\n=== {cls} ({img_path.name}) ===")
    print(f"  mean_brightness = {mean_b:.3f}")
    print(f"  very_dark(0.14) = {very_dark/total:.3%}  dark(0.18) = {dark_018/total:.3%}  dark(0.22) = {dark_022/total:.3%}")
    print(f"  mold_spot(tight)= {mold_spot/total:.3%}  mold_wide = {mold_wide/total:.3%}")
    print(f"  orange(tight)   = {orange/total:.3%}  orange_wide = {orange_wide/total:.3%}")
    print(f"  hue histogram (10-deg buckets):")
    for i in range(0, 36, 6):
        labels = [f"{i*10+j*10:3d}-{i*10+j*10+9:3d}:{hue_hist[i+j]:5d}" for j in range(6) if i+j < 36]
        print(f"    {' | '.join(labels)}")
