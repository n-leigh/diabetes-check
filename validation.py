"""
validation.py — server-side validation for the patient assessment form.

Client-side min/max attributes on the form help, but they're trivially
bypassed (browser devtools, direct POST, disabled JS) — so every field
is re-validated here regardless of what the browser already checked.
Returns (patient_dict, errors_list). If errors_list is non-empty,
patient_dict should NOT be trusted or saved.
"""

from __future__ import annotations  # keeps type hints safe on Python < 3.9

# (field, label, min, max, required, is_float)
FIELD_RULES = [
    ("BMI", "BMI", 10.0, 80.0, True, True),
    ("Age", "Age band", 1, 13, True, False),
    ("GenHlth", "General health", 1, 5, True, False),
    ("PhysHlth", "Poor physical health days", 0, 30, True, False),
    ("MentHlth", "Poor mental health days", 0, 30, True, False),
]

# Optional lab fields — validated only if the user actually provides a
# value; blank is fine and means "not measured / not entered".
OPTIONAL_LAB_FIELD_RULES = [
    ("LabHbA1c", "HbA1c", 3.0, 20.0, True),
    ("LabSystolicBP", "Systolic BP", 60, 250, False),
    ("LabLDL", "LDL cholesterol", 20, 400, False),
]

CHECKBOX_FIELDS = [
    "HighBP", "HighChol", "Smoker", "HeartDiseaseorAttack", "Stroke",
    "DiffWalk", "NoDocbcCost", "BlurryVision",
]

SELECT_FIELDS = {
    "Sex": [0, 1],
    "DiabetesDuration": [0, 1, 2, 3],
}


def validate_patient_form(form) -> tuple[dict, dict, list[str]]:
    """Returns (patient_dict, lab_values_dict, errors_list)."""
    patient = {}
    errors = []

    for field, label, lo, hi, required, is_float in FIELD_RULES:
        raw = form.get(field, "").strip()
        if raw == "":
            if required:
                errors.append(f"{label} is required.")
                continue
            raw = None

        if raw is not None:
            try:
                value = float(raw) if is_float else int(float(raw))
            except ValueError:
                errors.append(f"{label} must be a number.")
                continue

            if value < lo or value > hi:
                errors.append(f"{label} must be between {lo} and {hi}.")
                continue

            patient[field] = value

    for field in CHECKBOX_FIELDS:
        # checkboxes: absent/0/false = unchecked = 0, present/1 = 1
        val = form.get(field)
        patient[field] = 1 if val and str(val).strip().lower() not in ("0", "false", "off", "no") else 0

    for field, allowed in SELECT_FIELDS.items():
        raw = form.get(field, "")
        try:
            value = int(raw)
        except ValueError:
            errors.append(f"{field} must be selected.")
            continue
        if value not in allowed:
            errors.append(f"{field} has an invalid value.")
            continue
        patient[field] = value

    # optional lab values: blank is fine, but if provided must be in range
    lab_values = {}
    for field, label, lo, hi, is_float in OPTIONAL_LAB_FIELD_RULES:
        raw = form.get(field, "").strip()
        if raw == "":
            continue
        try:
            value = float(raw) if is_float else int(float(raw))
        except ValueError:
            errors.append(f"{label} must be a number.")
            continue
        if value < lo or value > hi:
            errors.append(f"{label} must be between {lo} and {hi}.")
            continue
        lab_values[field] = value

    return patient, lab_values, errors
