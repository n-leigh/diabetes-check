"""Build plain-language recommendations based on screening risk tiers."""

from typing import Dict, List, Optional

TIER_ORDER = {"Low": 0, "Moderate": 1, "High": 2}


def _highest_tier(*tiers: Optional[str]) -> str:
    best = "Low"
    for tier in tiers:
        if tier and TIER_ORDER.get(tier, 0) > TIER_ORDER[best]:
            best = tier
    return best


def build_recommendations(
    rule_results: Dict,
    lab_assessment: Optional[Dict] = None,
    patient: Optional[Dict] = None,
) -> Dict:
    """Return follow-up steps matched to elevated scores and reported answers."""
    patient = patient or {}
    cardiovascular = rule_results.get("cardiovascular", {}).get("label", "Low")
    nerves_and_feet = rule_results.get("neuropathy_mobility", {}).get("label", "Low")
    general_health = rule_results.get("general_burden", {}).get("label", "Low")
    eyes = rule_results.get("retinopathy", {}).get("label", "Low")
    lab_tier = lab_assessment["label"] if lab_assessment else None
    overall = _highest_tier(
        cardiovascular, nerves_and_feet, general_health, eyes, lab_tier
    )

    steps: List[Dict] = []

    if cardiovascular in ("Moderate", "High"):
        if patient.get("HighBP") == 1:
            steps.append({
                "title": "Review your blood pressure",
                "description": (
                    "You reported high blood pressure. Bring any recent "
                    "readings to your next visit. Ask your provider how often "
                    "to check it."
                ),
            })
        if patient.get("HighChol") == 1:
            steps.append({
                "title": "Review your cholesterol",
                "description": (
                    "You reported high cholesterol. Ask your provider whether "
                    "a cholesterol test is due and what your results mean."
                ),
            })
        if patient.get("Smoker") == 1:
            steps.append({
                "title": "Ask about help with smoking",
                "description": (
                    "You reported a smoking history. If you smoke now, ask "
                    "your clinic about support to quit or cut back."
                ),
            })
        if patient.get("HeartDiseaseorAttack") == 1 or patient.get("Stroke") == 1:
            steps.append({
                "title": "Discuss your heart or stroke history",
                "description": (
                    "Tell your provider about your past heart problem or "
                    "stroke. Ask what follow-up is right for you."
                ),
            })
        if not any(
            patient.get(field) == 1
            for field in ("HighBP", "HighChol", "Smoker", "HeartDiseaseorAttack", "Stroke")
        ):
            steps.append({
                "title": "Ask about a heart health check",
                "description": (
                    "Ask your provider whether blood pressure and cholesterol "
                    "checks are due."
                ),
            })

    if nerves_and_feet in ("Moderate", "High"):
        if patient.get("DiffWalk") == 1:
            steps.append({
                "title": "Talk about difficulty walking",
                "description": (
                    "You reported trouble walking or climbing stairs. Tell "
                    "your provider what is difficult and ask for a foot and "
                    "walking check."
                ),
            })
        if patient.get("PhysHlth", 0) >= 5:
            steps.append({
                "title": "Mention your physical health days",
                "description": (
                    f"You reported {patient['PhysHlth']} days of poor physical "
                    "health in the past month. Tell your provider how this "
                    "affects walking or daily tasks."
                ),
            })
        if not patient.get("DiffWalk") and patient.get("PhysHlth", 0) < 5:
            steps.append({
                "title": "Ask for a foot check",
                "description": (
                    "Ask your provider to check your feet and discuss any "
                    "numbness, tingling, or new pain."
                ),
            })
        else:
            steps.append({
                "title": "Check your feet each day",
                "description": (
                    "Look for cuts, blisters, or sores. Tell your clinic if "
                    "you find a new wound or a change in feeling."
                ),
            })

    if eyes in ("Moderate", "High"):
        vision_detail = (
            "You reported blurry vision or floaters. Tell the eye doctor "
            "when you noticed them."
            if patient.get("BlurryVision") == 1
            else "Ask for a dilated eye exam or retinal photo, even if your "
            "vision feels normal."
        )
        steps.append({
            "title": "Arrange an eye exam",
            "description": (
                f"{vision_detail} The eye result is less certain than the "
                "others. Please get an eye exam either way."
            ),
        })

    if general_health in ("Moderate", "High"):
        if patient.get("HighBP") == 1:
            steps.append({
                "title": "Ask about kidney tests",
                "description": (
                    "You reported high blood pressure. Ask your provider "
                    "whether a urine check and kidney blood test are due."
                ),
            })
        elif patient.get("DiabetesDuration", 0) >= 1:
            steps.append({
                "title": "Check when your kidney tests are due",
                "description": (
                    "Ask your clinic whether you are due for a urine check "
                    "and a kidney blood test."
                ),
            })
        if patient.get("MentHlth", 0) >= 15:
            steps.append({
                "title": "Ask for support with stress or mood",
                "description": (
                    f"You reported {patient['MentHlth']} days of poor mental "
                    "health in the past month. Tell your provider if this "
                    "makes daily care harder."
                ),
            })
        if patient.get("NoDocbcCost") == 1:
            steps.append({
                "title": "Ask about lower-cost care",
                "description": (
                    "You said cost has stopped you from seeing a doctor. Ask "
                    "your barangay health center about low-cost visits or "
                    "available assistance."
                ),
            })
        if not any(
            patient.get(field) == 1 for field in ("HighBP", "NoDocbcCost")
        ) and patient.get("DiabetesDuration", 0) < 1 and patient.get("MentHlth", 0) < 15:
            steps.append({
                "title": "Plan a general checkup",
                "description": (
                    "Bring this report to your doctor or barangay health "
                    "center. Ask what follow-up fits your health."
                ),
            })

    if lab_assessment and lab_tier in ("Moderate", "High"):
        details = lab_assessment.get("details", {})
        for lab_key, title, label, unit, question in (
            (
                "hba1c", "Review your 3-month sugar test",
                "3-month sugar test (HbA1c)", "%", "Ask what target is right for you.",
            ),
            (
                "systolic_bp", "Review your blood pressure result",
                "top blood pressure number", " mmHg",
                "Ask your provider what the reading means for you.",
            ),
            (
                "ldl", "Review your bad cholesterol result",
                "bad cholesterol (LDL)", " mg/dL",
                "Ask how it compares with your personal target.",
            ),
        ):
            reading = details.get(lab_key)
            if reading and reading.get("points", 0) > 0:
                steps.append({
                    "title": title,
                    "description": (
                        f"Your {label} result was {reading['value']}{unit}. "
                        f"Bring it to your next visit. {question}"
                    ),
                })

    if overall == "Low":
        headline = (
            "Your results look reassuring overall — keep up what you're doing."
        )
        steps.append({
            "title": "Stick with your healthy habits",
            "description": (
                "Regular activity, a balanced diet, and an annual checkup are "
                "great ways to stay ahead of complications, even when things "
                "look good now."
            ),
        })
    elif overall == "Moderate":
        headline = "A few areas are worth keeping an eye on."
        steps.append({
            "title": "Routine checkups still matter",
            "description": (
                "Even alongside the steps above, a yearly general checkup "
                "helps catch anything new early — often before it becomes "
                "noticeable."
            ),
        })
    else:
        headline = (
            "Some results may be useful to discuss at a healthcare visit."
        )
        steps.append({
            "title": "Routine checkups still matter",
            "description": (
                "Even alongside the steps above, a yearly general checkup "
                "helps catch anything new early — often before it becomes "
                "noticeable."
            ),
        })

    steps.append({
        "title": "About these results",
        "description": (
            "This tool estimates complication risk using statistical models "
            "trained on population health data. The result is intended for "
            "screening and education, not diagnosis. A higher result may "
            "justify discussing follow-up testing with a healthcare "
            "professional. A lower result does not rule out disease, and a "
            "higher result does not confirm disease."
        ),
    })

    return {
        "overall_tier": overall,
        "headline": headline,
        "steps": steps,
    }
