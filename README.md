# Web-Based Diabetes Complication Prediction System

Clinical rule matrix + trained classifier + Flask web app, trained on the
real CDC Diabetes Health Indicators dataset (BRFSS 2015), filtered to
diabetic-positive respondents — 35,346 rows, no missing values.

## Setup

```bash
pip install -r requirements.txt
```

## Project structure

```
rule_matrix.py          # clinical rule matrix (label generator + live scorer)
train_model.py          # loads data, applies rules, compares 3 classifiers per category, saves the best
database.py              # SQLite persistence for assessments
app.py                  # Flask web app (form -> rule matrix + model results, /history page)
data/
  generate_sample_data.py   # synthetic data generator (no longer needed, kept for reference)
  diabetes_dataset.csv      # REAL DATA: 35,346 diabetic-positive CDC/BRFSS respondents
templates/
  index.html             # patient input form
  result.html             # risk results page (shows rule matrix + model side by side)
  history.html            # list of past assessments, links to detail view
model/                   # trained .pkl files + training_summary.json (which model won, why)
diabetes_system.db       # created automatically on first run
```

## How to run right now

```bash
python3 train_model.py     # retrains + saves models (already run once on real data)
python3 app.py              # starts the web server
# open http://127.0.0.1:5000
```

## Current results (best of 3 classifiers per category, real data, 35,346 rows, 80/20 split)

| Category | Best model | Accuracy | Notes |
|---|---|---|---|
| Cardiovascular | Random Forest | 98.7% | Decision Tree alone gets 84% (still your most "realistic" single-model story); ensemble closes the gap because it has enough capacity to approximate the rule's threshold interactions closely |
| Neuropathy/Mobility | Decision Tree | 100% | Simple rule logic dominated by `DiffWalk` — any of the 3 models reconstructs it almost exactly |
| General Burden | Decision Tree | 100% | Same cause — few features, deterministic thresholds |

Full comparison across all 3 algorithms for all 3 categories is saved in
`model/training_summary.json` — pull straight from there for your
results-chapter comparison table.

## Live demo checklist for next week

1. `pip install -r requirements.txt`
2. `python3 train_model.py` (already run — re-run only if you change the
   dataset or rule matrix)
3. `python3 app.py` → open http://127.0.0.1:5000
4. Submit a few assessments with different values (try one with all boxes
   unchecked and low BMI for a "Low" result, one with everything checked
   and high BMI for "High" — makes for a clean before/after demo)
5. Click **History** to show persistence — this is your strongest visual
   proof the "web-based system" part of the title is real, not just a
   script
6. Click **View** on a past record to show it's independently retrievable

Also note for your limitations section: 5,122 of the 35,346 rows are
exact duplicates across the feature set. Expected — BRFSS features are
coarse/categorical, so distinct respondents legitimately share identical
profiles. Kept rather than dropped, to avoid selection bias.

## Recent updates

- **Footer** added site-wide via `base.html`, with nav links and a plain-language disclaimer
- **Gauge fixed** — the circular risk-score rings were using a hand-rotated 270° arc that
  visually misrepresented the percentage and had overlapping text. Replaced with a standard
  full-circle progress ring (`templates/result.html`) — verified the dash-offset math directly
  against expected values before shipping.
- **Form redesigned for a general audience, not just clinicians**: Age and General Health are
  now dropdowns with plain-language options (no more guessing what "band 6" means), every field
  has a one-line plain-English explanation, and required fields use light "e.g. 24.5" placeholder
  hints instead of silently pre-filled fake values that could look like real data.
- **Recommendations engine** (`recommendations.py`) — turns the risk results into plain-language
  next steps per category, always ending with a "this isn't medical advice" reminder. Wired into
  both `/predict` and `/history/<id>`.
- **Language pass**: "Assess Another Patient" → "Check Someone Else", since this system is meant
  for anyone checking their own risk, not just healthcare staff reviewing a patient's chart.

## Routes

- `/` — Home landing page (hero, stats, category overview)
- `/assessment` — the actual risk assessment form
- `/predict` — POST target for the form, shows results
- `/history` — list of past assessments
- `/history/<id>` — a single past assessment's results
- `/about` — Study Background + Ethics/Limitations/Disclaimer

## Design

Restyled to match the "DiaBeates" Figma Make design (teal/sky gradient
theme, Plus Jakarta Sans + Inter fonts, circular risk gauges, your custom
logo) — Tailwind CSS via CDN, no build step needed. `templates/base.html`
holds the shared navbar and design tokens; `index.html`, `result.html`,
and `history.html` extend it. A compact hero banner (adapted from the
Figma design's Home page) sits above the form, using our real numbers
(35,346 real patient records, 3 categories, 3 classifiers compared) —
not the placeholder marketing stats from the original design.

## Optional lab values (HbA1c, Systolic BP, LDL)

The CDC dataset used to train the classifiers is self-reported survey
data — it doesn't contain lab values, so the trained models can't use
them. Instead, `rule_matrix.py`'s `compute_lab_assessment()` scores any
lab values a user enters directly against cited ADA/NHANES thresholds,
shown as a separate "Lab-Based Clinical Assessment" card, fully optional
and independent of the 3 survey-based categories above it. If a
panelist asks about HbA1c/lab data: this is your answer — it's there,
cited, and deliberately kept separate from the classifier rather than
silently blended in, since the classifier was never trained on it.

## About page

`/about` covers the actual Study Background (accurate to what this
system does — not the original Figma placeholder copy) and a substantive
Ethics, Limitations & Disclaimer section written specifically for this
project: rule-derived training labels (not real diagnosed outcomes),
CDC/BRFSS dataset scope and bias, and local-only data handling. R&D
Phases, Research Significance, and Team sections were intentionally
left out — add them later with real specifics if you want the full page.

## This week's to-do list

1. **Explain the near-100% categories, don't hide them.** Because labels
   are generated by the rule matrix from the same features the classifier
   sees, categories with simple threshold logic (few dominant features)
   will hit ~100% accuracy — the model is exactly reconstructing the rule.
   Cardiovascular (more features, wider point spread) looks more realistic.
   State this plainly in your methodology/limitations section: the trained
   model's value is generalization/speed, not discovering new patterns,
   since the ground truth itself came from human-authored rules rather
   than diagnosed outcomes.

2. **Cite your rule matrix properly.** The thresholds in `rule_matrix.py`
   are simplified for a 4-week scope — in your methodology chapter, cite:
   - ADA Standards of Care in Diabetes 2026, Section 12
     (Retinopathy, Neuropathy, and Foot Care)
   - General cardiovascular risk literature for diabetic patients
     (hypertension, dyslipidemia, smoking, obesity, age)

3. **Optional bonus (if time allows in week 3-4):** compare Decision Tree
   against Logistic Regression and Random Forest in `train_model.py` —
   easy to add, and gives you a model-comparison section for your results
   chapter, which panels tend to like.

4. **Add a database** (SQLite is enough) to store each assessed patient's
   inputs + results, if your rubric expects a persistent records feature.

## Team split suggestion

- 1–2 people: tune the rule matrix thresholds if the label distribution
  looks off, explore feature importances (`clf.feature_importances_`) for
  the results chapter, write up the methodology/limitations sections
  above
- 1–2 people: extend `app.py` / templates (styling, patient history page,
  maybe login)
- 1 person: documentation (Chapters 1–5), keep it updated continuously,
  not just in week 4
