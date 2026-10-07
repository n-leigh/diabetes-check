"""Build practical, plain-language steps for the results page."""

from typing import Dict, Optional

TIER_ORDER = {"Low": 0, "Moderate": 1, "High": 2}


def _highest_tier(*tiers: Optional[str]) -> str:
    best = "Low"
    for tier in tiers:
        if tier and TIER_ORDER.get(tier, 0) > TIER_ORDER[best]:
            best = tier
    return best


def build_recommendations(
    rule_results: Dict, lab_assessment: Optional[Dict] = None
) -> Dict:
    """Return the specific, localized steps from the earlier results page."""
    overall = _highest_tier(
        rule_results.get("cardiovascular", {}).get("label", "Low"),
        rule_results.get("neuropathy_mobility", {}).get("label", "Low"),
        rule_results.get("general_burden", {}).get("label", "Low"),
        rule_results.get("retinopathy", {}).get("label", "Low"),
        lab_assessment.get("label") if lab_assessment else None,
    )

    return {
        "overall_tier": overall,
        "headline": (
            "Small, practical habits that help keep your sugar and blood vessels healthy."
        ),
        "steps": [
            {
                "title": "Rice portions",
                "description": (
                    "Try cutting white rice to 1 cup per meal. "
                    "Brown or red rice helps even more."
                ),
                "icon": "plate",
            },
            {
                "title": "Walking after meals",
                "description": (
                    "Take a 10 to 15 minute walk after eating lunch or dinner."
                ),
                "icon": "shoe",
            },
            {
                "title": "Merienda choices",
                "description": (
                    "Swap salty sari-sari store chips and fried snacks for "
                    "boiled saba banana, fresh fruit, or unsalted peanuts."
                ),
                "icon": "companion",
            },
            {
                "title": "Drink water",
                "description": (
                    "Drink cold water instead of softdrinks, sweet milk teas, "
                    "or instant 3-in-1 coffee."
                ),
                "icon": "water",
            },
            {
                "title": "Clinic visit",
                "description": (
                    "Bring this printout to your nearest barangay health center "
                    "or doctor."
                ),
                "icon": "doctor",
            },
        ],
    }
