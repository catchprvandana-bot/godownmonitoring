"""Quick smoke-test: run _analyze_image against synthetic dataset samples.

Usage (from project root):
    python -m backend.test_classify
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import _analyze_image


def test_samples():
    dataset_dir = PROJECT_ROOT / "ml" / "dataset" / "val"
    classes = ["healthy", "mold", "pest_damage", "discoloration"]
    
    total = 0
    correct = 0
    errors = {}

    for cls in classes:
        cls_dir = dataset_dir / cls
        if not cls_dir.exists():
            print(f"  ⚠ {cls}/ not found, skipping")
            continue

        images = sorted(cls_dir.glob("*.jpg"))[:10]  # test first 10 per class
        cls_correct = 0

        for img_path in images:
            img_bytes = img_path.read_bytes()
            label, confidence = _analyze_image(img_bytes)
            total += 1
            if label == cls:
                cls_correct += 1
                correct += 1
            else:
                errors.setdefault(cls, []).append(
                    f"  {img_path.name} -> {label} ({confidence:.0%})"
                )
                print(f"    WRONG: {img_path.name} expected={cls} got={label} conf={confidence:.0%}")

        print(f"  {cls:15s}: {cls_correct}/{len(images)} correct")

    if total > 0:
        print(f"\n  Overall: {correct}/{total} ({correct/total:.0%})")
    else:
        print(f"\n  Overall: 0/0 (0%)")

    if errors:
        print("\n  Misclassifications:")
        for cls, msgs in errors.items():
            print(f"    [{cls}]:")
            for m in msgs:
                print(f"      {m}")


if __name__ == "__main__":
    print("Testing _analyze_image against synthetic validation set...\n")
    test_samples()
