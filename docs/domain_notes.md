# Domain validation notes (Person C)

These are placeholder-but-defensible numbers already wired into `backend/risk.py`.
Your job before the pitch: tighten them with real citations/sources if time allows,
and be ready to defend them if judges push. The reasoning below is what makes the
demo sound credible instead of arbitrary — use it in the narration.

## Why these categories

`healthy / mold / pest_damage / discoloration` — chosen because they're the four
conditions actually visible in an RGB image of stored grain/produce without needing
lab equipment:

- **Mold/fungal growth** (e.g. Aspergillus, Penicillium on paddy) — visually distinct:
  white/grey/black fuzzy patches, clumping of grains.
- **Pest damage** (rice weevil, pulse beetle / bruchid) — visible as small bore holes,
  frass (insect waste) dust, or live insects on the surface.
- **Discoloration** — yellowing/browning from moisture damage or age, distinct from
  active mold (no fuzzy growth, just color shift).
- **Healthy** — the baseline/negative class, needed so the model doesn't force a
  disease label on every image.

These are the same categories a warehouse inspector would use in a manual visual
check — the model is automating what already happens informally.

## Why these thresholds (Tamil Nadu paddy & pulses storage)

| Signal | Threshold | Why |
|---|---|---|
| Humidity | >70% RH = elevated risk, >75% RH = high risk | Paddy grain re-absorbs ambient moisture above ~70% RH, pushing internal grain moisture past the ~14% safe-storage line. Above that line, Aspergillus/Penicillium mold can establish within days, especially in Tamil Nadu's humid coastal/monsoon conditions. |
| Temperature | >30C = elevated, >32C = high risk | Grain-storage pests (rice weevil, pulse beetle) are largely dormant below ~25-28C but breed actively above ~30-32C; higher temperature also accelerates fungal metabolic rate once moisture is already present. |
| Gas (CO2 proxy) | >550ppm = elevated, >700ppm = high risk | Sound, dry grain has very low respiration and produces little CO2. A rising CO2 reading in an enclosed zone is an early sign of active biological activity (mold or insects) — often measurable *before* visible spoilage, making it a leading indicator rather than a lagging one. |

Paddy and pulses have slightly different safe-moisture profiles (pulses are more
susceptible to bruchid/pulse-beetle infestation at similar humidity levels) — if there's
time, split the thresholds per crop type instead of one shared rule. Not required for
the MVP demo, but a good "we know this is a simplification" talking point for judges.

## Pitch narration (2-3 sentences)

> "These aren't arbitrary numbers — paddy grain re-absorbs moisture from humid air
> above roughly 70% relative humidity, which is the tipping point where mold can
> establish within days. Temperatures above 30-32C wake up dormant storage pests
> like rice weevil and pulse beetle. And a rising CO2 reading tells us something is
> already metabolically active in that zone — often before any visible sign of
> spoilage — which is what lets us alert before the loss happens, not after."

## Open questions to resolve if time allows

- Confirm exact safe-moisture-content numbers for paddy vs. pulses from an ICAR/FCI
  storage guideline rather than general knowledge, and cite it in the deck.
- Confirm whether rice weevil vs. pulse beetle have meaningfully different temperature
  thresholds worth splitting in the rule.
- One line on cold-storage applicability (the pitch claims scalability to cold storage —
  note that these RH/temp thresholds are specific to ambient/warehouse storage, not
  refrigerated units, and would need separate thresholds there).
