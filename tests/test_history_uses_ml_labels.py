import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app


def test_history_uses_ml_labels_not_rule_labels():
    records = [{
        "display_index": 1,
        "id": 1,
        "created_at": "2026-09-29T12:00:00+00:00",
        "patient": {"BMI": 24.5},
        "rule_results": {
            "cardiovascular": {"label": "High"},
            "general_burden": {"label": "Low"},
            "neuropathy_mobility": {"label": "High"},
            "retinopathy": {"label": "Moderate"},
        },
        "model_results": {
            "cardiovascular": "Higher Estimated Risk",
            "general_burden": "Lower Estimated Risk",
            "neuropathy_mobility": "Higher Estimated Risk",
            "retinopathy": "Moderate Estimated Risk",
        },
    }]

    with app.test_request_context("/history"):
        html = app.jinja_env.get_template("history.html").render(
            records=records,
            categories=["cardiovascular", "general_burden", "neuropathy_mobility", "retinopathy"],
            show_archived=False,
            sort_order="desc",
            csrf_token=lambda: "fake-token",
        )

    assert "Higher Estimated Risk" in html
    assert "Lower Estimated Risk" in html
    assert "Moderate Estimated Risk" in html
    assert "High" not in html.split("Higher Estimated Risk")[0][-50:]  # sanity check around rendered row
