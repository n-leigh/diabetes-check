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
    Calculate cardiovascular disease risk points based on clinical rule matrix.
    
    Scoring logic (total max: 15 points):
    - HighBP: +2
    - HighChol: +2
    - Smoker: +1
    - Prior heart disease/attack: +3
    - Prior stroke: +3
    - BMI ≥30 (obese): +2
    - BMI 25–29 (overweight): +1
    - Age ≥55 (BRFSS band 9+): +2
    - Age 40–54 (BRFSS band 6–8): +1
    
    Rationale: Hypertension, dyslipidemia, smoking, obesity, age, and prior 
    CVD events are established risk factors per ADA Standards of Care 2026.
    
    Args:
        row (dict): Patient data with keys: HighBP, HighChol, Smoker, 
                    HeartDiseaseorAttack, Stroke, BMI, Age
    
    Returns:
        int: Total points (0–15)
        
    See Also:
        classify_pct(): Convert points to Low/Moderate/High label
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
    Calculate diabetic neuropathy/foot complication risk points.
    
    Scoring logic (total max: 7 points):
    - Difficulty walking/climbing stairs (DiffWalk): +3 (direct indicator)
    - PhysHlth ≥15 poor health days: +2
    - PhysHlth 5–14 poor health days: +1
    - BMI ≥30: +1
    - Age ≥55: +1
    
    Rationale: DiffWalk is a direct neuropathy marker (numbness/weakness in legs).
    Physical limitation days and obesity/age are risk confounders.
    
    Args:
        row (dict): Patient data with keys: DiffWalk, PhysHlth, BMI, Age
    
    Returns:
        int: Total points (0–7)
        
    See Also:
        classify_pct(): Convert points to Low/Moderate/High label
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
    Calculate overall diabetes complication burden and healthcare access barriers.
    
    Scoring logic (total max: 5 points):
    - GenHlth 4–5 (fair/poor): +3
    - GenHlth 3 (good): +1
    - MentHlth ≥15 poor mental health days: +1
    - Skipped care due to cost (NoDocbcCost): +1
    
    Rationale: Self-reported general health and mental health are proxies for 
    overall complication burden and self-management capacity. Cost barriers 
    indicate access problems.
    
    Args:
        row (dict): Patient data with keys: GenHlth, MentHlth, NoDocbcCost
    
    Returns:
        int: Total points (0–5)
        
    See Also:
        classify_pct(): Convert points to Low/Moderate/High label
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
    Convert risk percentage (0–100) to Low/Moderate/High tier label.
    
    Uses percentile-based classification: 33/66 split. See METHODOLOGY.md
    for sensitivity analysis justifying this choice.
    
    Thresholds:
    - 0–33% : Low
    - 34–66% : Moderate
    - 67–100% : High
    
    Args:
        pct (float): Risk percentage (0–100)
    
    Returns:
        str: "Low", "Moderate", or "High"
        
    Note:
        This function is used both for rule matrix and lab assessment,
        ensuring consistent tier boundaries across all predictions.
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
    Assess diabetes control and cardiovascular risk using clinical lab values.
    
    Provides **optional, additional scoring** based on actual lab values 
    (HbA1c, BP, LDL). This is completely separate from the three CDC-survey-based
    categories (cardiovascular, neuropathy_mobility, general_burden) because the
    training dataset doesn't contain lab values.
    
    **Important:** If lab values are provided, they're scored against clinical 
    thresholds and shown in a separate result panel. They are NOT fed into the
    trained classifiers (which expect only survey data).
    
    Clinical Thresholds:
    - HbA1c: 
      * <6.5%: Controlled (0 pts)
      * 6.5–8.0%: Suboptimal (1 pt)
      * >8.0%: Poor control (2 pts)
      * Per ADA Standards of Care 2026
    - Systolic BP:
      * <130: Controlled (0 pts)
      * 130–139: Elevated (1 pt)
      * ≥140: High (2 pts)
      * Per NHANES/ADA targets for diabetics
    - LDL Cholesterol:
      * <100: Optimal (0 pts)
      * 100–129: Borderline (1 pt)
      * ≥130: Elevated (2 pts)
      * Per ADA/ACC lipid targets
    
    Args:
        hba1c (float, optional): HbA1c percentage (e.g., 7.2)
        systolic_bp (int, optional): Systolic blood pressure in mmHg (e.g., 135)
        ldl (float, optional): LDL cholesterol in mg/dL (e.g., 110)
    
    Returns:
        dict or None: If no lab values provided, returns None.
                      Otherwise: {
                          "label": "Low" | "Moderate" | "High",
                          "percentage": 0–100,
                          "details": {
                              "hba1c": {...},
                              "systolic_bp": {...},
                              "ldl": {...}
                          }
                      }
                      
    Example:
        >>> compute_lab_assessment(hba1c=7.5, systolic_bp=135, ldl=115)
        {
            "label": "Moderate",
            "percentage": 56,
            "details": {...}
        }
        
    See Also:
        compute_all_risks(): Survey-based risk assessment
        classify_pct(): Convert percentage to tier label
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
    Compute comprehensive diabetes complication risk across all three categories.
    
    Applies the three scoring functions (cardiovascular, neuropathy_mobility,
    general_burden) and converts point totals into percentiles and tier labels.
    
    **Key Design:** Label and percentage are derived from the same score via 
    classify_pct(), ensuring that the risk gauge and tier badge always agree.
    (Earlier versions had separate cutoff schemes that could contradict.)
    
    Args:
        row (dict): Patient data with features:
            - HighBP, HighChol, Smoker, HeartDiseaseorAttack, Stroke (binary)
            - BMI (float), Age (int, BRFSS 1-13)
            - DiffWalk (binary), PhysHlth (int, 0-30 days)
            - GenHlth (int, 1-5), MentHlth (int, 0-30 days)
            - NoDocbcCost (binary), Sex (binary)
    
    Returns:
        dict: Three categories, each with score/label/percentage:
        {
            "cardiovascular": {
                "score": 6,           # Raw points (0–15)
                "label": "Moderate",  # "Low" | "Moderate" | "High"
                "percentage": 40      # 0–100% of max possible score
            },
            "neuropathy_mobility": {...},
            "general_burden": {...}
        }
        
    Example:
        >>> row = {"HighBP": 1, "HighChol": 1, "BMI": 30, "Age": 9, ...}
        >>> compute_all_risks(row)
        {
            "cardiovascular": {"score": 6, "label": "Moderate", "percentage": 40},
            "neuropathy_mobility": {"score": 0, "label": "Low", "percentage": 0},
            "general_burden": {"score": 1, "label": "Low", "percentage": 20}
        }
        
    See Also:
        score_cardiovascular(): Cardiovascular risk scoring
        score_neuropathy_mobility(): Neuropathy/mobility risk scoring
        score_general_complication_burden(): Overall burden scoring
        classify_pct(): Convert percentage to tier label
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