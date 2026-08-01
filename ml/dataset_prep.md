# Dataset prep (Person A)

We will not find a ready-made "stored grain spoilage" dataset. Adapt existing plant
disease datasets as a proxy instead:

- **PlantVillage** (Kaggle: `emmarex/plantdisease` or similar mirrors) — clean, lab-condition
  leaf images across many crop diseases. Good source for `mold` (fungal disease classes)
  and `healthy`.
- **PlantDoc** (GitHub: `pratikkayal/PlantDoc-Dataset`) — real-world, messier field images.
  Good source for `discoloration` and general robustness (mixes better with real godown
  photo conditions than PlantVillage alone).

## Target classes

Remap source classes into exactly these 4 (must match `CLASS_NAMES` in both
`ml/train_spoilage_model.py` and `backend/main.py`):

| Our class | Pull from source dataset |
|---|---|
| `healthy` | Healthy/uninfected leaf classes |
| `mold` | Fungal disease classes (blight, rust, mildew, mold) |
| `pest_damage` | Insect/pest-damage classes if present in PlantDoc; otherwise use visibly chewed/holed leaf images |
| `discoloration` | Nutrient-deficiency or non-fungal discoloration classes |

## Steps

1. Download both datasets, extract locally (or directly into a Colab-mounted Drive folder).
2. Write a small remap script (or do it by hand for a hackathon-sized subset) that copies
   images from source class folders into `dataset/train/<our_class>/` and
   `dataset/val/<our_class>/` (80/20 split is fine).
3. Keep it small — a few hundred images per class is enough to demo transfer learning
   converging well in `ml/train_spoilage_model.py`. Don't try to use the full dataset;
   it'll just slow down Colab for no demo benefit.
4. Sanity-check class balance — wildly uneven folders (2000 healthy vs. 40 mold) will bias
   the model toward always predicting healthy.
5. Once trained, copy `spoilage_model.h5` into `backend/model/` — the backend picks it up
   automatically on restart (falls back to mock predictions if the file isn't there, so the
   rest of the team is never blocked waiting on this).

## Stretch goal — confidence-aware output

Already implemented on the backend side (`backend/risk.py` / `backend/main.py`): if the
top prediction's confidence is below 60%, the API returns `"uncertain"` instead of a hard
label and flags it for manual check. Nothing extra needed from the model itself — just
make sure the model returns calibrated-ish softmax probabilities (it will, by default).
