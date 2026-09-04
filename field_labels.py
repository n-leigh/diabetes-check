"""
field_labels.py — human-readable translations for the coded form values.

The form stores BRFSS-style codes (Age band 1-13, GenHlth 1-5, etc.) since
that's what the trained models expect. This module translates those codes
back to plain language for display contexts like the printable summary,
where "Age band 9" means nothing to the person reading it.
"""

AGE_RANGES = {
    "1": "18–24", "2": "25–29", "3": "30–34", "4": "35–39", "5": "40–44",
    "6": "45–49", "7": "50–54", "8": "55–59", "9": "60–64", "10": "65–69",
    "11": "70–74", "12": "75–79", "13": "80 or older",
}

HEALTH_RATINGS = {
    "1": "Excellent", "2": "Very good", "3": "Good", "4": "Fair", "5": "Poor",
}

SEX_LABELS = {"0": "Female", "1": "Male"}

DURATION_LABELS = {
    "0": "<1 year", "1": "1–4 years", "2": "5–9 years", "3": "10+ years",
}

CHECKBOX_LABELS = {
    "HighBP": "High blood pressure",
    "HighChol": "High cholesterol",
    "Smoker": "Smoker",
    "HeartDiseaseorAttack": "Prior heart disease/attack",
    "Stroke": "Prior stroke",
    "DiffWalk": "Difficulty walking/climbing stairs",
    "NoDocbcCost": "Skipped care due to cost",
    "BlurryVision": "Frequent blurry vision / floaters",
}


def describe_patient(patient: dict) -> dict:
    """Returns a display-friendly version of the raw patient dict."""
    return {
        "BMI": patient.get("BMI"),
        "Age": AGE_RANGES.get(str(patient.get("Age")), "—"),
        "GenHlth": HEALTH_RATINGS.get(str(patient.get("GenHlth")), "—"),
        "Sex": SEX_LABELS.get(str(patient.get("Sex")), "—"),
        "DiabetesDuration": DURATION_LABELS.get(str(patient.get("DiabetesDuration")), "—"),
        "PhysHlth": patient.get("PhysHlth"),
        "MentHlth": patient.get("MentHlth"),
        "risk_factors": [
            label for field, label in CHECKBOX_LABELS.items()
            if patient.get(field) == 1
        ],
    }
