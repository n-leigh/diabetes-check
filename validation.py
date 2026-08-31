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
    "DiffWalk", "NoDocbcCost",
]

SELECT_FIELDS = {
    "Sex": [0, 1],
}


def validate_patient_form(form) -> tuple[dict, dict, list[str]]:
    """
    Server-side validation for patient assessment form submission.
    
    **Important:** All form inputs are validated on the server, regardless 
    of client-side checks. Browser validation is trivially bypassed (devtools, 
    disabled JS, direct POST), so this function is the authoritative check.
    
    Validates:
    1. Required numeric fields (BMI, Age, health ratings)
    2. Optional lab fields (HbA1c, BP, LDL) — blank is OK
    3. Checkbox fields (binary 0/1)
    4. Select fields (allowed values only)
    
    Args:
        form (dict-like): Form submission data (e.g., Flask request.form)
        
    Returns:
        tuple: (patient_dict, lab_values_dict, errors_list)
            - patient_dict (dict): Validated patient features; empty if errors
            - lab_values_dict (dict): Validated lab values; empty if none provided
            - errors_list (list[str]): User-friendly error messages; empty if valid
            
    Example (valid):
        >>> form = {'BMI': '27.5', 'Age': '8', 'GenHlth': '3', ...}
        >>> patient, labs, errors = validate_patient_form(form)
        >>> if not errors:
        ...     predictions = app.predict(patient, labs)
        
    Example (invalid):
        >>> form = {'BMI': 'abc', 'Age': '20'}  # 'abc' is not a number, Age out of range
        >>> patient, labs, errors = validate_patient_form(form)
        >>> errors
        ['BMI must be a number.', 'Age must be between 1 and 13.']
        >>> patient  # Empty dict; don't use
        {}
        
    Implementation:
    - Required fields: Must be present and in valid range
    - Optional fields: Absent or blank = skipped; if present, validated
    - Checkboxes: Absent = 0, present = 1
    - Selects: Must be in allowed_values
    
    See Also:
        FIELD_RULES: Defines required numeric fields and ranges
        OPTIONAL_LAB_FIELD_RULES: Defines optional lab fields
        CHECKBOX_FIELDS: List of checkbox field names
        SELECT_FIELDS: Dict of select field names and allowed values
    """
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
        # checkboxes: absent = unchecked = 0, present = 1
        patient[field] = 1 if form.get(field) else 0

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
