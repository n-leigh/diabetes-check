# Web-Based Diabetes Complication Prediction System (DiaBeates)

A Flask web app combining a clinically-cited rule matrix with trained
classification models to estimate diabetes complication risk across
three categories: Cardiovascular, Neuropathy/Mobility, and General
Complication Burden. Both methods run on every submission and are shown
side by side.

## Data sources (updated to 2021-2024)

The project originally used the 2015 CDC Diabetes Health Indicators
dataset. It's since been rebuilt on more recent BRFSS (Behavioral Risk
Factor Surveillance System) data from 2021-2024, matching the "data no
older than 5 years" requirement.

This wasn't a simple file swap. BRFSS rotates some questions between a
core and an optional module each year, and no single recent year (or
combination of years) contains every variable the original rule matrix
needed. Specifically:

- High blood pressure / high cholesterol questions were asked in 2021
  and 2023, but not in 2022 or 2024.
- A difficulty-walking / mobility question wasn't in any of the
  2021-2024 pre-cleaned extracts available, but was present in a
  separate, raw (unprocessed) 2024 BRFSS file.

Since BRFSS surveys a different, anonymous group of people every year,
there's no valid way to attach one year's respondent's answer onto a
different year's respondent's record — that would be fabricating data
that specific person never actually gave. So each category now trains
on whichever real, internally-consistent respondent pool actually has
the variables that category needs:

| Category | Data source | Real respondents (diabetic-positive) |
|---|---|---|
| Cardiovascular | 2021 + 2023 BRFSS | 92,622 |
| General Complication Burden | 2021 + 2022 + 2023 + 2024 BRFSS | 196,518 |
| Neuropathy / Mobility | Raw 2024 BRFSS extract | 56,683 |

`build_datasets_2021_2024.py` builds all three from the raw source
files (see `data_2024_update/`, gitignored due to size — the raw 2024
CSV alone is 400MB+). The derived, already-cleaned CSVs it produces
(`data/cardio_dataset.csv`, `data/general_burden_dataset.csv`,
`data/neuropathy_dataset.csv`) are a few MB each and are what
`train_model.py` actually reads — those are what should be committed to
git, not the raw sources.

**Real consequence of this:** each category's classifier now trains on
a different, honestly-scoped subset of features (whatever its data
source actually has). This is documented per-category in
`model/training_summary.json` under `"features"`, and `app.py` reads
that automatically — it selects the right columns per model rather than
assuming one shared feature set.

## Setup

```bash
pip install -r requirements.txt
```

## Project structure

```
rule_matrix.py                  # clinical rule matrix (label generator + live scorer)
build_datasets_2021_2024.py     # builds the 3 category-specific datasets from raw BRFSS sources
train_model.py                  # loads each category's dataset, trains + compares 3 classifiers, saves the best
database.py                     # SQLite persistence (normalized schema, session-scoped)
app.py                          # Flask web app
recommendations.py              # plain-language "what to do" engine based on risk tiers
field_labels.py                 # translates coded form values to plain language (used by the print view)
validation.py                   # server-side form validation
data/
  cardio_dataset.csv            # 2021+2023 real respondents
  general_burden_dataset.csv    # 2021-2024 real respondents
  neuropathy_dataset.csv        # raw 2024 real respondents
templates/
  home.html, assessment.html, result.html, history.html, about.html, print_result.html, base.html
model/                          # trained .pkl files + training_summary.json
diabetes_system.db              # created automatically on first run (gitignored)
```

## How to run

```bash
python3 build_datasets_2021_2024.py   # only needed once, or if you get new raw source data
python3 train_model.py                 # trains + saves models
python3 app.py                         # starts the web server
# open http://127.0.0.1:5000
```

## Current results (best of 3 classifiers per category, 80/20 split)

| Category | Best model | Accuracy | Notes |
|---|---|---|---|
| Cardiovascular | Random Forest | 99.0% | Decision Tree alone gets 92.3% — the more "realistic" single-model story, since this category has the most features and widest point spread |
| Neuropathy/Mobility | Decision Tree | 100% | Simple rule logic dominated by difficulty-walking — any model reconstructs it almost exactly |
| General Burden | Decision Tree | 100% | Same cause — few features, deterministic thresholds |

Full comparison across all 3 algorithms for all 3 categories, plus which
dataset and features each category used, is saved in
`model/training_summary.json`.

**For your limitations section:** the near-100% categories reflect
models learning to reconstruct simple, human-authored threshold rules,
not discovering new medical patterns — because the training labels
themselves came from the rule matrix, not confirmed diagnoses. State
this proactively; it's explained in full on `/about`.

## Backend / Database

SQLite, normalized into 4 tables (`database.py`):

- **`assessments`** — raw inputs, an anonymous `session_id`, and the
  `rule_matrix_version` that scored it, plus an `archived` flag
- **`risk_results`** — one row per (assessment, category): rule score,
  rule label, model name, model prediction, and model confidence
  (`predict_proba` max probability)
- **`lab_assessments`** — one row per assessment, only if lab values
  were provided
- **`feedback`** — "was this helpful?" responses, tied to an assessment

**Privacy:** every visitor gets an anonymous session cookie. History,
detail view, print view, archive/delete, and feedback routes all verify
the requested record actually belongs to the requesting session before
acting — tested directly with two separate simulated clients to confirm
one cannot view, print, archive, delete, or leave feedback on the
other's data by guessing an ID.

**Auto-migration:** `init_db()` checks SQLite's `PRAGMA user_version`
against the app's expected schema. A mismatch (e.g. an old copy of
`diabetes_system.db`) triggers an automatic rebuild of the app's tables
— no manual steps needed.

## History page: archive & delete

Users can archive (reversible, moves out of the main list) or
permanently delete (cascades across all 4 tables, no orphaned rows) any
of their own past assessments. Both actions check session ownership
first — a different session cannot archive or delete someone else's
record.

## Printable results

Every result has a "Print / Save Result" button linking to
`/history/<id>/print` — a standalone template (`print_result.html`),
not the styled page dumped to a printer. Translates coded values to
plain language, includes recommendations and lab assessment if present,
and ends with the same "not medical advice" disclaimer.

## Optional lab values (HbA1c, Systolic BP, LDL)

None of the training datasets contain real lab values, so the
classifiers can't use them. `rule_matrix.py`'s `compute_lab_assessment()`
scores any lab values a user enters directly against cited ADA/NHANES
thresholds, shown as a separate card, fully optional and independent of
the 3 model-based categories.

## Routes

- `/` — Home landing page
- `/assessment` — the risk assessment form
- `/predict` — POST target, shows results
- `/history` — list of past assessments (active/archived tabs)
- `/history/<id>` — a single assessment's results
- `/history/<id>/print` — printable summary
- `/history/<id>/archive`, `/history/<id>/delete` — POST actions
- `/feedback/<id>` — POST, records a helpful/not-helpful response
- `/about` — Study Background + Ethics/Limitations/Disclaimer

## About page

`/about` covers the real Study Background and a substantive Ethics,
Limitations & Disclaimer section: rule-derived training labels (not
diagnosed outcomes), BRFSS dataset scope, and local-only data handling.
Worth updating to mention the multi-year, per-category data sourcing
described above.
