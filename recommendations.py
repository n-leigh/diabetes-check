"""
recommendations.py — turns risk tiers into plain-language next steps.

Deliberately general-wellness in tone (not clinical directives): "consider
talking to a doctor about X" rather than "take medication Y". Every
recommendation set ends with a reminder that this is not medical advice.
Designed to be readable by someone with no healthcare background, since
this system is meant for the general public checking their own risk, not
only clinicians reviewing a patient's chart.
"""

from typing import Dict, List, Optional

TIER_ORDER = {"Low": 0, "Moderate": 1, "High": 2}


def _highest_tier(*tiers: str) -> str:
    best = "Low"
    for t in tiers:
        if t and TIER_ORDER.get(t, 0) > TIER_ORDER[best]:
            best = t
    return best


def build_recommendations(rule_results: Dict, lab_assessment: Optional[Dict] = None) -> Dict:
    """
    Returns:
    {
      "overall_tier": "Moderate",
      "headline": "...",
      "items": [ {"title": ..., "description": ...}, ... ]
    }
    """
    cv_tier = rule_results.get("cardiovascular", {}).get("label", "Low")
    neuro_tier = rule_results.get("neuropathy_mobility", {}).get("label", "Low")
    burden_tier = rule_results.get("general_burden", {}).get("label", "Low")
    lab_tier = lab_assessment["label"] if lab_assessment else None

    overall = _highest_tier(cv_tier, neuro_tier, burden_tier, lab_tier)

    items: List[Dict] = []

    # Overall headline by tier
    if overall == "Low":
        headline = "Your results look reassuring overall — keep up what you're doing."
    elif overall == "Moderate":
        headline = "A few areas are worth keeping an eye on."
    else:
        headline = "Some results here are worth acting on soon."

    # Cardiovascular guidance
    if cv_tier in ("Moderate", "High"):
        items.append({
            "title": "Consider a heart health check-in",
            "description": "Ask a healthcare provider about checking your blood pressure and cholesterol if it's "
                            "been a while. Regular movement (even a daily walk) and cutting back on smoking, if it "
                            "applies to you, both support heart health.",
        })

    # Neuropathy / mobility guidance
    if neuro_tier in ("Moderate", "High"):
        items.append({
            "title": "Keep an eye on your feet and mobility",
            "description": "Numbness, tingling, or new difficulty walking are worth mentioning to a doctor. "
                            "A quick daily check of your feet for cuts or sores, and comfortable, well-fitting "
                            "shoes, are simple habits that help.",
        })

    # General burden guidance
    if burden_tier in ("Moderate", "High"):
        items.append({
            "title": "A general wellness check could help",
            "description": "If day-to-day health or stress has been wearing on you, a routine checkup is a good "
                            "next step. If you're struggling emotionally, talking to someone you trust — a friend, "
                            "counselor, or doctor — can make a real difference.",
        })

    # Lab-based guidance
    if lab_assessment and lab_tier in ("Moderate", "High"):
        items.append({
            "title": "Bring your lab results to your next appointment",
            "description": "Share the values you entered here with a healthcare provider — they can interpret "
                            "them in the context of your full health picture and advise on next steps.",
        })

    # Baseline / low-risk guidance — always shown, adjusted in tone
    if overall == "Low":
        items.append({
            "title": "Stick with your healthy habits",
            "description": "Regular activity, a balanced diet, and an annual checkup are great ways to stay ahead "
                            "of complications, even when things look good now.",
        })
    else:
        items.append({
            "title": "Routine checkups still matter",
            "description": "Even alongside the steps above, a yearly general checkup helps catch anything new "
                            "early — often before it becomes noticeable.",
        })

    return {
        "overall_tier": overall,
        "headline": headline,
        "steps": items,
    }
