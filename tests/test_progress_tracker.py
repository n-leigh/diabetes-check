import unittest
from datetime import datetime, timedelta, timezone

from progress_tracker import SHORT_GAP_THRESHOLD, build_progress_view, to_display_datetime


def record(created_at, labels, archived=False, patient=None, lab_assessment=None,
           rule_matrix_version="1.0", risk_drivers=None):
    return {
        "id": created_at,
        "created_at": created_at,
        "archived": archived,
        "patient": patient or {},
        "lab_assessment": lab_assessment,
        "rule_matrix_version": rule_matrix_version,
        "risk_drivers": risk_drivers or [],
        "rule_results": {
            category: {"label": label}
            for category, label in labels.items()
        },
    }


ALL_DOMAINS = {
    "cardiovascular": "Low",
    "general_burden": "Moderate",
    "neuropathy_mobility": "High",
    "retinopathy": "Low",
}


class ProgressTrackerViewModelTests(unittest.TestCase):
    def test_zero_and_one_check_states(self):
        self.assertTrue(build_progress_view([])["empty"])
        view = build_progress_view([record("2026-11-04T00:00:00+00:00", ALL_DOMAINS)])
        self.assertIsNotNone(view["baseline"])
        self.assertEqual(view["baseline"]["statuses"][0]["status"]["label"], "Good")

    def test_status_changes_and_no_change(self):
        first = record("2026-11-01T00:00:00+00:00", ALL_DOMAINS)
        second_labels = dict(ALL_DOMAINS, cardiovascular="Moderate", neuropathy_mobility="Low")
        view = build_progress_view([
            first,
            record("2026-11-04T00:00:00+00:00", second_labels),
        ])
        messages = {row["title"]: row["message"] for row in view["summary_rows"]}
        self.assertEqual(messages["Heart"], "Heart: Moved from Good to Check.")
        self.assertEqual(messages["Kidneys"], "Kidneys: No change, Check.")
        self.assertEqual(messages["Nerves & Feet"], "Nerves & Feet: Moved from See a doctor to Good.")

    def test_missing_domain_is_not_compared_as_a_status(self):
        first = record("2026-11-01T00:00:00+00:00", {"cardiovascular": "Low"})
        second = record("2026-11-04T00:00:00+00:00", {})
        view = build_progress_view([first, second])
        rows = {row["title"]: row["message"] for row in view["summary_rows"]}
        self.assertEqual(rows["Heart"], "Heart: no result this time (it was Good before).")
        self.assertEqual(view["grid"][0]["statuses"][0]["label"], "Not available")

    def test_gap_boundaries_and_short_gap_threshold(self):
        start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        labels = {key: "Low" for key, _title in (
            ("cardiovascular", "Heart"),
            ("general_burden", "Kidneys"),
            ("neuropathy_mobility", "Nerves"),
            ("retinopathy", "Eyes"),
        )}
        view = build_progress_view([
            record(start, labels),
            record(start + timedelta(minutes=2), labels),
            record(start + timedelta(days=8), labels),
        ])
        entries = view["timelines"][0]["entries"]
        self.assertEqual(entries[1]["gap_label"], "a few minutes later")
        self.assertEqual(entries[2]["gap_label"], "7 days later")
        self.assertFalse(view["short_gap_notice"])
        self.assertEqual(SHORT_GAP_THRESHOLD, timedelta(days=7))

    def test_sqlite_text_and_postgres_datetime_and_year_label(self):
        text_time = "2025-12-30T16:00:00+00:00"
        datetime_time = datetime(2026, 1, 1, 16, tzinfo=timezone.utc)
        labels = {key: "Low" for key, _title in (
            ("cardiovascular", "Heart"),
            ("general_burden", "Kidneys"),
            ("neuropathy_mobility", "Nerves"),
            ("retinopathy", "Eyes"),
        )}
        view = build_progress_view([
            record(text_time, labels),
            record(datetime_time, labels),
        ], now=datetime(2026, 11, 4, tzinfo=timezone.utc))
        self.assertIn("2025", view["grid"][1]["time_label"])
        self.assertIn("2026", view["grid"][0]["time_label"])
        self.assertEqual(to_display_datetime(datetime_time).year, 2026)

    def test_archived_records_are_marked_and_limited_grid(self):
        labels = {key: "Low" for key, _title in (
            ("cardiovascular", "Heart"),
            ("general_burden", "Kidneys"),
            ("neuropathy_mobility", "Nerves"),
            ("retinopathy", "Eyes"),
        )}
        records = [
            record(f"2026-10-{day:02d}T00:00:00+00:00", labels, archived=day == 3)
            for day in range(1, 9)
        ]
        view = build_progress_view(records, include_archived=True)
        self.assertEqual(len(view["grid"]), 6)
        self.assertTrue(any(item["archived"] for item in view["grid"]))
        self.assertIn("including archived", view["included_phrase"])

    def test_changed_answers_drivers_trends_and_version_notice(self):
        first = record(
            "2026-10-01T00:00:00+00:00",
            ALL_DOMAINS,
            patient={"BMI": 31, "HighBP": 1, "Smoker": 1},
            lab_assessment={"details": {
                "hba1c": {"value": 8.1},
                "systolic_bp": {"value": 145},
            }},
            rule_matrix_version="1.0",
            risk_drivers=["High blood pressure", "Active Smoking History"],
        )
        second = record(
            "2026-11-01T00:00:00+00:00",
            ALL_DOMAINS,
            patient={"BMI": 27, "HighBP": 0, "Smoker": 1},
            lab_assessment={"details": {
                "hba1c": {"value": 7.4},
                "systolic_bp": {"value": 132},
                "ldl": {"value": 110},
            }},
            rule_matrix_version="2.0",
            risk_drivers=["Active Smoking History", "Elevated BMI"],
        )
        view = build_progress_view([first, second])
        comparison = view["comparison"]
        changes = {item["label"]: item for item in comparison["changed_answers"]}
        self.assertEqual(changes["BMI"]["before"], "31")
        self.assertEqual(changes["High blood pressure"]["after"], "No")
        self.assertEqual(changes["Bad cholesterol (LDL)"]["before"], "Not entered")
        self.assertEqual(comparison["drivers"]["appeared"], ["Elevated BMI"])
        self.assertEqual(comparison["drivers"]["disappeared"], ["High blood pressure"])
        self.assertTrue(comparison["scoring_updated"])
        self.assertEqual({trend["name"] for trend in view["trends"]},
                         {"BMI", "LabHbA1c", "LabSystolicBP", "LabLDL"})

    def test_compare_ids_select_any_two_checks(self):
        records = [
            record(f"2026-10-{day:02d}T00:00:00+00:00", ALL_DOMAINS)
            for day in (1, 2, 3)
        ]
        view = build_progress_view(records, compare_ids=["2026-10-01T00:00:00+00:00", "2026-10-02T00:00:00+00:00"])
        self.assertEqual(view["comparison"]["before"]["date"], "Oct 1, 08:00")
        self.assertEqual(view["comparison"]["after"]["date"], "Oct 2, 08:00")


if __name__ == "__main__":
    unittest.main()
