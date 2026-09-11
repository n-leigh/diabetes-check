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
    Generate plain-language clinical recommendations based on risk tiers.
    
    Synthesizes risk predictions (from rules and/or models) into actionable
    guidance for patients. Recommendations are deliberately general-wellness 
    in tone ("consider talking to a doctor") rather than clinical directives 
    ("take medication X"), suitable for general public use.
    
    Logic:
    1. Determine overall tier: max of (cardiovascular, neuropathy, burden, lab) tiers
    2. Generate tier-specific headline
    3. For each category with Moderate/High risk, add relevant recommendation
    4. If lab values provided and Moderate/High, suggest bringing results to doctor
    5. Add baseline wellness reminder (adjusted tone per tier)
    6. Return all as structured steps
    
    Args:
        rule_results (dict): Output from compute_all_risks(), e.g.:
            {
                "cardiovascular": {"label": "Moderate", ...},
                "neuropathy_mobility": {"label": "Low", ...},
                "general_burden": {"label": "High", ...}
            }
        lab_assessment (dict, optional): Output from compute_lab_assessment(), e.g.:
            {
                "label": "Moderate",
                "percentage": 50,
                ...
            }
            If None, lab assessment is skipped.
    
    Returns:
        dict: Recommendation structure:
        {
            "overall_tier": "Moderate",  # Highest tier across all categories
            "headline": "A few areas...",  # Tier-specific headline
            "steps": [
                {
                    "title": "Consider a heart health check-in",
                    "description": "Ask a healthcare provider about..."
                },
                ...
            ]
        }
        
    Example:
        >>> results = compute_all_risks({...})
        >>> recs = build_recommendations(results)
        >>> print(recs['headline'])
        "Some results here are worth acting on soon."
        >>> for step in recs['steps']:
        ...     print(f"- {step['title']}")
        
    Design Notes:
    - Headings and steps are non-alarming but clear
    - Each step ends with "talk to a doctor" or equivalent
    - Lab assessment treated as independent panel (optional)
    - Always includes baseline wellness reminder
    - Tone adjusts based on overall_tier (Low vs. High)
    
    See Also:
        compute_all_risks(): Generates rule_results input
        compute_lab_assessment(): Generates lab_assessment input
    """
    cv_tier = rule_results.get("cardiovascular", {}).get("label", "Low")
    neuro_tier = rule_results.get("neuropathy_mobility", {}).get("label", "Low")
    burden_tier = rule_results.get("general_burden", {}).get("label", "Low")
    retino_tier = rule_results.get("retinopathy", {}).get("label", "Low")
    lab_tier = lab_assessment["label"] if lab_assessment else None

    overall = _highest_tier(cv_tier, neuro_tier, burden_tier, retino_tier, lab_tier)

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

    # Diabetic Retinopathy / Vision guidance
    if retino_tier in ("Moderate", "High"):
        items.append({
            "title": "Schedule a dilated eye examination",
            "description": "Diabetic eye changes and macular swelling can develop without noticeable pain. "
                           "An annual comprehensive dilated eye exam or retinal photography with an optometrist "
                           "or ophthalmologist is essential for catching early retinopathy before vision is affected. "
                           "Note: The retinopathy screening model has wider uncertainty than the other models "
                           "and should be considered experimental.",
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

    # Universal clinical disclaimer — always shown
    items.append({
        "title": "About these results",
        "description": "This tool estimates complication risk using statistical models trained on "
                        "population health data. The result is intended for screening and education, "
                        "not diagnosis. A higher result may justify discussing follow-up testing with a "
                        "healthcare professional. A lower result does not rule out disease, and a "
                        "higher result does not confirm disease.",
    })

    return {
        "overall_tier": overall,
        "headline": headline,
        "steps": items,
    }
