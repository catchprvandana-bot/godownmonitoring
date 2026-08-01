"""Spoilage classifier training script.

Trains a MobileNetV2-based transfer-learning model on the 4-class spoilage
dataset (healthy / mold / pest_damage / discoloration).

Two modes:
  1. Synthetic dataset (default, CPU-friendly, ~5-10 min):
       python ml/train_spoilage_model.py
     First run `python ml/generate_synthetic_dataset.py` to create the data.

  2. Real PlantVillage/PlantDoc data (better accuracy, needs Colab GPU):
       python ml/train_spoilage_model.py --dataset /path/to/real/dataset --epochs 12

Output: backend/model/spoilage_model.h5
The FastAPI backend picks it up automatically on next restart.

Class names MUST match backend/main.py CLASS_NAMES — do not reorder.
"""

import argparse
from pathlib import Path

IMG_SIZE = (224, 224)
BATCH_SIZE = 32
DEFAULT_EPOCHS = 8  # Enough for synthetic; bump to 12 for real data on Colab
CLASS_NAMES = ["healthy", "mold", "pest_damage", "discoloration"]  # must match backend/main.py

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_DIR = PROJECT_ROOT / "ml" / "dataset"
OUTPUT_PATH = PROJECT_ROOT / "backend" / "model" / "spoilage_model.h5"


def load_datasets(dataset_dir: Path, batch_size: int):
    import tensorflow as tf  # pyright: ignore[reportMissingImports, reportMissingModuleSource]
    from tensorflow.keras import layers  # pyright: ignore[reportMissingImports, reportMissingModuleSource]

    opts = dict(image_size=IMG_SIZE, batch_size=batch_size, label_mode="categorical", class_names=CLASS_NAMES)
    train_ds = tf.keras.utils.image_dataset_from_directory(str(dataset_dir / "train"), **opts)
    val_ds   = tf.keras.utils.image_dataset_from_directory(str(dataset_dir / "val"),   **opts)

    normalize = layers.Rescaling(1.0 / 255)
    train_ds = (train_ds.map(lambda x, y: (normalize(x), y), num_parallel_calls=tf.data.AUTOTUNE)
                        .cache()
                        .shuffle(1000)
                        .prefetch(tf.data.AUTOTUNE))
    val_ds   = (val_ds.map(lambda x, y: (normalize(x), y), num_parallel_calls=tf.data.AUTOTUNE)
                      .cache()
                      .prefetch(tf.data.AUTOTUNE))
    return train_ds, val_ds


def build_model():
    import tensorflow as tf  # pyright: ignore[reportMissingImports, reportMissingModuleSource]
    from tensorflow.keras import layers, models  # pyright: ignore[reportMissingImports, reportMissingModuleSource]
    from tensorflow.keras.applications import MobileNetV2  # pyright: ignore[reportMissingImports, reportMissingModuleSource]

    base = MobileNetV2(input_shape=(224, 224, 3), include_top=False, weights="imagenet")
    base.trainable = False  # Transfer learning — freeze base

    model = models.Sequential([
        base,
        layers.GlobalAveragePooling2D(),
        layers.Dense(128, activation="relu"),
        layers.Dropout(0.3),
        layers.Dense(len(CLASS_NAMES), activation="softmax"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def main():
    parser = argparse.ArgumentParser(description="Train spoilage classifier")
    parser.add_argument("--dataset",  default=str(DEFAULT_DATASET_DIR),
                        help=f"Dataset root containing train/ and val/ (default: {DEFAULT_DATASET_DIR})")
    parser.add_argument("--epochs",   type=int, default=DEFAULT_EPOCHS,
                        help=f"Training epochs (default: {DEFAULT_EPOCHS})")
    parser.add_argument("--batch",    type=int, default=BATCH_SIZE, help="Batch size")
    parser.add_argument("--output",   default=str(OUTPUT_PATH),
                        help=f"Where to save the .h5 file (default: {OUTPUT_PATH})")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset)
    if not dataset_dir.exists():
        raise FileNotFoundError(
            f"Dataset directory not found: {dataset_dir}\n"
            "Run `python ml/generate_synthetic_dataset.py` first."
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"📂 Dataset   : {dataset_dir.resolve()}")
    print(f"💾 Output    : {output_path.resolve()}")
    print(f"🔄 Epochs    : {args.epochs}")

    train_ds, val_ds = load_datasets(dataset_dir, args.batch)
    model = build_model()
    model.summary()

    # Optional: callbacks for cleaner output
    import tensorflow as tf  # pyright: ignore[reportMissingImports, reportMissingModuleSource]
    callbacks = [
        tf.keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ReduceLROnPlateau(patience=2, factor=0.5, verbose=1),
    ]

    model.fit(train_ds, validation_data=val_ds, epochs=args.epochs, callbacks=callbacks)

    model.save(str(output_path))
    print(f"\n✅ Model saved → {output_path.resolve()}")
    print("Restart the backend server to pick up the new model.")


if __name__ == "__main__":
    main()
