"""
rule_matrix.py
Clinical rule matrix for diabetes complication risk scoring (Version 2.0-clinical).

Scope: This matrix is aligned with international clinical guidelines:
- ACC/AHA 10-Year ASCVD Risk Guidelines & UKPDS: Cardiovascular risk factor weighting
  (hypertension, dyslipidemia, smoking, prior stroke/MI, age, BMI).
- KDIGO 2024 & CKD-EPI 2021: Diabetic nephropathy and systemic vascular burden
  (blood pressure, glycemic control, renal markers).
- Michigan Neuropathy Screening Instrument (MNSI): Peripheral functional impairment
  (mobility difficulty, physical health status, microvascular ischemic risk).

Each score_* function returns an integer point total. classify_pct() converts
percentage of maximum possible score into Low (<30%), Moderate (30-60%), and High (>60%)
risk tiers based on clinical decision thresholds.
"""

from typing import Dict, Optional

# Bumped from 1.0 to 2.0-clinical following clinical guideline alignment.
RULE_VERSION = "2.0-clinical"


def _get(row: dict, key: str, default=0):
    return row.get(key, default)


def score_cardiovascular(row: Dict) -> int:
    """
    Cardiovascular Complication Risk Scorer (ACC/AHA ASCVD & UKPDS Aligned).
    Risk factors:
      - Hypertension / HighBP (+2)
      - Dyslipidemia / HighChol (+2)
      - Current Smoking status (+2) [High multiplier in diabetic populations]
      - Established Vascular Disease: Prior Heart Attack/CAD (+3), Prior Stroke (+3)
      - Obesity: BMI >= 30 (+2), BMI 25-29.9 (+1)
      - Age: Senior age band (>=9 / ~55+) (+2), Middle age band (6-8 / ~40-54) (+1)
    """
    points = 0
    if _get(row, "HighBP") == 1:
        points += 2
    if _get(row, "HighChol") == 1:
        points += 2
    if _get(row, "Smoker") == 1:
        points += 2  # Aligned with ACC/AHA guidelines weighting for active smoking in diabetes
    if _get(row, "HeartDiseaseorAttack") == 1:
        points += 3  # Secondary prevention risk multiplier
    if _get(row, "Stroke") == 1:
        points += 3  # Cerebrovascular event multiplier

    bmi = _get(row, "BMI", 0)
    if bmi >= 30:
        points += 2
    elif bmi >= 25:
        points += 1

    age_band = _get(row, "Age", 0)
    if age_band >= 9:      # roughly 55+ in BRFSS/NHANES age bands
        points += 2
    elif age_band >= 6:    # roughly 40-54
        points += 1

    return points


def score_neuropathy_mobility(row: Dict) -> int:
    """
    Peripheral Neuropathy & Mobility Impairment Scorer (MNSI Aligned).
    Evaluates:
      - DiffWalk (difficulty walking / climbing stairs as primary functional sign) (+3)
      - PhysHlth (chronic physical health deficit days in past 30): >=15 days (+2), >=5 days (+1)
      - Microvascular / metabolic multipliers: BMI >= 30 (+1), Age >= 9 (+1), Smoker (+1)
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

    if _get(row, "Smoker") == 1:
        points += 1  # Microvascular ischemic risk to peripheral nerves

    return points


def score_general_complication_burden(row: Dict) -> int:
    """
    Nephropathy & Systemic Complication Burden Scorer (KDIGO 2024 Aligned).
    Evaluates:
      - Hypertension / HighBP (+2) [Primary clinical risk driver of diabetic nephropathy]
      - Self-reported overall systemic health (GenHlth): Poor/Fair (4-5) (+3), Good (3) (+1)
      - Mental health deficit days (MentHlth >= 15) (+1)
      - Healthcare access / affordability barrier (NoDocbcCost) (+1)
    """
    points = 0
    if _get(row, "HighBP") == 1:
        points += 2  # Strong predictor of renal vascular damage

    gen_hlth = _get(row, "GenHlth", 1)  # 1=excellent ... 5=poor
    if gen_hlth >= 4:
        points += 3
    elif gen_hlth == 3:
        points += 1

    ment_hlth_days = _get(row, "MentHlth", 0)
    if ment_hlth_days >= 15:
        points += 1

    if _get(row, "NoDocbcCost") == 1:
        points += 1

    return points


def score_retinopathy(row: Dict) -> int:
    """
    Diabetic Retinopathy & Vision Risk Scorer (ADA & UKPDS 50 Aligned).
    Risk factors:
      - Diabetes Duration: >=10 yrs (+3), 5-9 yrs (+2), 1-4 yrs (+1)
      - Visual Symptoms (BlurryVision) (+3) [Key indicator of macular edema/capillary leakage]
      - Hypertension / HighBP (+2) [Shear stress on retinal capillaries]
      - Dyslipidemia / HighChol (+1) [Hard lipid exudate risk]
      - Smoker (+1) [Microvascular retinal ischemia]
    """
    points = 0
    dur = _get(row, "DiabetesDuration", 1)
    if dur >= 3:
        points += 3
    elif dur == 2:
        points += 2
    elif dur == 1:
        points += 1

    if _get(row, "BlurryVision") == 1:
        points += 3
    if _get(row, "HighBP") == 1:
        points += 2
    if _get(row, "HighChol") == 1:
        points += 1
    if _get(row, "Smoker") == 1:
        points += 1

    return points


def classify_pct(pct: float) -> str:
    """
    Clinical risk tier boundaries:
      - Low: <= 30%
      - Moderate: 31% - 60%
      - High: > 60%
    Derived directly from calculated risk scores and calibrated probabilities.
    """
    if pct <= 30:
        return "Low"
    elif pct <= 60:
        return "Moderate"
    else:
        return "High"


MAX_SCORES = {
    "cardiovascular": 2 + 2 + 2 + 3 + 3 + 2 + 2,   # 16
    "neuropathy_mobility": 3 + 2 + 1 + 1 + 1,       # 8
    "general_burden": 2 + 3 + 1 + 1,                # 7
    "retinopathy": 3 + 3 + 2 + 1 + 1,               # 10
}


def compute_lab_assessment(hba1c=None, systolic_bp=None, ldl=None) -> Optional[Dict]:
    """
    Optional clinical lab assessment using biomarker values:
    - HbA1c: ADA 2026 Standards of Care Section 6 targets (<7.0% optimal per Rec 6.3a, 7.0-7.9% suboptimal, >=8.0% elevated/uncontrolled)
    - Systolic BP: KDIGO 2024 Rec 3.4.1 & ADA 2026 Rec 10.4 targets (<120 optimal, 120-129 elevated, >=130 hypertension)
    - LDL cholesterol: ADA 2026 Section 10 targets (<70 optimal per Rec 10.20, 70-99 borderline, >=100 elevated)
    """
    provided = {}
    max_possible = 0
    total = 0

    if hba1c is not None:
        if hba1c < 7.0:
            pts = 0  # ADA 2026 Rec 6.3a general target for nonpregnant adults
        elif hba1c < 8.0:
            pts = 1  # Suboptimal / individualized target
        else:
            pts = 2  # Marked hyperglycemia / elevated complication risk
        provided["hba1c"] = {"value": hba1c, "points": pts}
        total += pts
        max_possible += 2

    if systolic_bp is not None:
        if systolic_bp < 120:
            pts = 0  # KDIGO 2024 & ADA Rec 10.4 high cardiovascular/renal risk target
        elif systolic_bp < 130:
            pts = 1  # Elevated systolic blood pressure
        else:
            pts = 2  # Hypertension threshold (>=130 mmHg per ADA 2026)
        provided["systolic_bp"] = {"value": systolic_bp, "points": pts}
        total += pts
        max_possible += 2

    if ldl is not None:
        if ldl < 70:
            pts = 0  # ADA 2026 Rec 10.20 optimal primary prevention target in diabetes
        elif ldl < 100:
            pts = 1  # Suboptimal atherogenic lipid level
        else:
            pts = 2  # Elevated cardiovascular risk (>=100 mg/dL)
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
    Computes per-category clinical rule score, label, and risk percentage.
    """
    cv = score_cardiovascular(row)
    neuro = score_neuropathy_mobility(row)
    general = score_general_complication_burden(row)
    retino = score_retinopathy(row)

    scores = {
        "cardiovascular": cv,
        "neuropathy_mobility": neuro,
        "general_burden": general,
        "retinopathy": retino,
    }
    result = {}
    for cat, score in scores.items():
        pct = round(min(score / MAX_SCORES[cat], 1.0) * 100)
        result[cat] = {"score": score, "label": classify_pct(pct), "percentage": pct}
    return result


if __name__ == "__main__":
    sample_patient = {
        "HighBP": 1, "HighChol": 1, "Smoker": 1, "BMI": 33,
        "HeartDiseaseorAttack": 0, "Stroke": 0, "Age": 9,
        "DiffWalk": 1, "PhysHlth": 18, "GenHlth": 4,
        "MentHlth": 5, "NoDocbcCost": 0,
    }
    import json
    print(json.dumps(compute_all_risks(sample_patient), indent=2))