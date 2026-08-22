"""
rule_matrix.py
Clinical rule matrix for diabetes complication risk scoring.

Scope: This matrix is built to match features available in the CDC Diabetes
Health Indicators dataset (BRFSS survey) — it deliberately avoids HbA1c /
diabetes-duration-based rules (classic nephropathy/retinopathy criteria)
because that dataset doesn't carry those fields. If your team later swaps
in a dataset that DOES have HbA1c, duration, or blood pressure readings
(systolic/diastolic numeric, not just HighBP flag), extend this file with
a nephropathy/retinopathy scorer using the same pattern.

Each score_* function returns an integer point total. classify() converts
points into a Low/Moderate/High label. This same logic is used twice:
  1. Offline, to generate ground-truth labels for training the classifier
     (see train_model.py)
  2. Live, in the Flask app, as a transparent "rule matrix" explanation
     shown alongside the model's prediction.

Cite in your methodology chapter:
- ADA Standards of Care in Diabetes 2026, Section 12 (Retinopathy,
  Neuropathy, and Foot Care) — hypertension, dyslipidemia, and chronic
  hyperglycemia as complication risk factors.
- General cardiovascular risk literature — hypertension, high cholesterol,
  smoking, obesity, and age as CVD risk multipliers in diabetic patients.
"""

from typing import Dict

# Bump this whenever scoring logic or thresholds change. Stored alongside
# every saved assessment so historical records stay interpretable even if
# the rule matrix is later revised — a record scored under v1.0 shouldn't
# be silently reinterpreted as if it were scored under v1.1's thresholds.
RULE_VERSION = "1.0"


def _get(row: dict, key: str, default=0):
    return row.get(key, default)


def score_cardiovascular(row: Dict) -> int:
    """
    Risk factors: HighBP, HighChol, Smoker, BMI, prior HeartDiseaseorAttack
    or Stroke, and Age band.
    Expects CDC-style binary flags (0/1) plus BMI (numeric) and Age
    (BRFSS age band code 1-13, roughly 18 -> 80+).
    """
    points = 0
    if _get(row, "HighBP") == 1:
        points += 2
    if _get(row, "HighChol") == 1:
        points += 2
    if _get(row, "Smoker") == 1:
        points += 1
    if _get(row, "HeartDiseaseorAttack") == 1:
        points += 3
    if _get(row, "Stroke") == 1:
        points += 3
    bmi = _get(row, "BMI", 0)
    if bmi >= 30:
        points += 2
    elif bmi >= 25:
        points += 1
    age_band = _get(row, "Age", 0)
    if age_band >= 9:      # roughly 55+ in BRFSS age bands
        points += 2
    elif age_band >= 6:    # roughly 40-54
        points += 1
    return points


def score_neuropathy_mobility(row: Dict) -> int:
    """
    Proxy for neuropathy / diabetic foot complications using DiffWalk
    (difficulty walking/climbing stairs), PhysHlth (poor physical health
    days in past 30), BMI, and Age.
    """
    points = 0
    if _get(row, "DiffWalk") == 1:
        points += 3
    phys_hlth_days = _get(row, "PhysHlth", 0)
    if phys_hlth_days >= 15:
        points += 2
    elif phys_hlth_days >= 5:
        points += 1
    bmi = _get(row, "BMI", 0)
    if bmi >= 30:
        points += 1
    age_band = _get(row, "Age", 0)
    if age_band >= 9:
        points += 1
    return points


def score_general_complication_burden(row: Dict) -> int:
    """
    Broad complication burden proxy using self-reported general health,
    mental health days, and healthcare access barriers.
    """
    points = 0
    gen_hlth = _get(row, "GenHlth", 1)  # 1=excellent ... 5=poor
    if gen_hlth >= 4:
        points += 3
    elif gen_hlth == 3:
        points += 1
    ment_hlth_days = _get(row, "MentHlth", 0)
    if ment_hlth_days >= 15:
        points += 1
    if _get(row, "NoDocbcCost") == 1:  # skipped care due to cost
        points += 1
    return points


def classify_pct(pct: float) -> str:
    """
    Single, consistent tier boundary used for every category (and the lab
    assessment below) — the label is always derived directly from the
    same percentage shown in the gauge, so the two can never disagree.
    """
    if pct <= 33:
        return "Low"
    elif pct <= 66:
        return "Moderate"
    else:
        return "High"


MAX_SCORES = {
    "cardiovascular": 2 + 2 + 1 + 3 + 3 + 2 + 2,   # 15
    "neuropathy_mobility": 3 + 2 + 1 + 1,           # 7
    "general_burden": 3 + 1 + 1,                    # 5
}


def compute_lab_assessment(hba1c=None, systolic_bp=None, ldl=None) -> Dict:
    """
    Optional, clinically-cited assessment using actual lab values, kept
    fully separate from the 3 CDC-survey-based categories above. The CDC
    Diabetes Health Indicators dataset (used to train the classifiers)
    doesn't contain HbA1c, blood pressure readings, or lipid panels — it's
    self-reported survey data, not lab draws — so this section can't be
    fed into the trained classifiers without an entirely different
    dataset. Instead, when a user supplies real lab values, this function
    scores them directly against cited clinical thresholds. It's meant to
    be shown as an additional, clearly-labeled panel, not merged into the
    cardiovascular/neuropathy/general_burden scores above.

    Returns None if no lab values were supplied at all.

    Thresholds cited:
    - HbA1c: ADA Standards of Care in Diabetes glycemic targets
      (<6.5% controlled, 6.5-8.0% suboptimal, >8.0% poor control)
    - Systolic BP: NHANES study threshold of 127 mmHg for accelerated
      kidney damage progression in type 2 diabetes; ADA target <130 mmHg
    - LDL cholesterol: ADA/ACC lipid targets (<100 mg/dL optimal,
      100-129 borderline, >=130 elevated)
    """
    provided = {}
    max_possible = 0
    total = 0

    if hba1c is not None:
        if hba1c < 6.5:
            pts = 0
        elif hba1c < 8.0:
            pts = 1
        else:
            pts = 2
        provided["hba1c"] = {"value": hba1c, "points": pts}
        total += pts
        max_possible += 2

    if systolic_bp is not None:
        if systolic_bp < 127:
            pts = 0
        elif systolic_bp < 140:
            pts = 1
        else:
            pts = 2
        provided["systolic_bp"] = {"value": systolic_bp, "points": pts}
        total += pts
        max_possible += 2

    if ldl is not None:
        if ldl < 100:
            pts = 0
        elif ldl < 130:
            pts = 1
        else:
            pts = 2
        provided["ldl"] = {"value": ldl, "points": pts}
        total += pts
        max_possible += 2

    if not provided:
        return None

    pct = round((total / max_possible) * 100)
    label = classify_pct(pct)

    return {
        "label": label,
        "percentage": pct,
        "score": total,
        "max_score": max_possible,
        "details": provided,
    }


def compute_all_risks(row: Dict) -> Dict[str, Dict]:
    """
    Returns per-category score + label + a 0-100 percentage, e.g.:
    {
      "cardiovascular": {"score": 6, "label": "Moderate", "percentage": 40},
      ...
    }
    Label and percentage are derived from the exact same number via
    classify_pct(), so the gauge and the tier badge can never disagree —
    an earlier version had two uncoordinated cutoff schemes that could
    contradict each other; fixed here.
    """
    cv = score_cardiovascular(row)
    neuro = score_neuropathy_mobility(row)
    general = score_general_complication_burden(row)

    scores = {"cardiovascular": cv, "neuropathy_mobility": neuro, "general_burden": general}
    result = {}
    for cat, score in scores.items():
        pct = round(min(score / MAX_SCORES[cat], 1.0) * 100)
        result[cat] = {"score": score, "label": classify_pct(pct), "percentage": pct}
    return result


if __name__ == "__main__":
    # quick manual sanity check
    sample_patient = {
        "HighBP": 1, "HighChol": 1, "Smoker": 1, "BMI": 33,
        "HeartDiseaseorAttack": 0, "Stroke": 0, "Age": 9,
        "DiffWalk": 1, "PhysHlth": 18, "GenHlth": 4,
        "MentHlth": 5, "NoDocbcCost": 0,
    }
    import json
    print(json.dumps(compute_all_risks(sample_patient), indent=2))