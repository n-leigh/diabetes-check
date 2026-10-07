"""
evaluate_calibration.py
Post-training calibration and threshold evaluation for all four complication models.

Loads the saved ClinicalRiskWrapper .pkl artifacts and the deterministic holdout
split (random_state=42, test_size=0.2) WITHOUT retraining. Reports binary metrics
at both stored screening and referral cutoffs, sweeps thresholds from 0.20–0.80,
and produces calibration tables, subgroup reliability checks, and a threshold
recommendation identifying the highest-recall operating point with precision ≥ 0.60.

Outputs are written to evaluation_results/.

Usage:
    python evaluate_calibration.py
"""

import os
import json
import csv
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss,
    confusion_matrix,
)

from train_model import (
    load_cardiovascular_data,
    load_nephropathy_data,
    load_neuropathy_mobility_data,
    load_retinopathy_data,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
OUTPUT_DIR = os.path.join(BASE_DIR, "evaluation_results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TASKS = {
    "cardiovascular": {
        "loader": load_cardiovascular_data,
        "label": "Cardiovascular (ACC/AHA)",
    },
    "general_burden": {
        "loader": load_nephropathy_data,
        "label": "Nephropathy & CKD (KDIGO)",
    },
    "neuropathy_mobility": {
        "loader": load_neuropathy_mobility_data,
        "label": "Neuropathy & Mobility (MNSI)",
    },
    "retinopathy": {
        "loader": load_retinopathy_data,
        "label": "Retinopathy (ADA)",
    },
}


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def threshold_metrics(y_true, probability, threshold):
    """Binary classification metrics at a single threshold."""
    predicted = (probability >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()

    sensitivity = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    f1 = (
        2 * precision * sensitivity / (precision + sensitivity)
        if precision + sensitivity
        else 0.0
    )

    return {
        "threshold": round(float(threshold), 4),
        "accuracy": round((tp + tn) / len(y_true), 4),
        "sensitivity": round(sensitivity, 4),
        "specificity": round(specificity, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def tier_metrics(y_true, probability, screening_threshold, referral_threshold):
    """Report the wrapper's three clinical tiers against the binary endpoint."""
    predicted_tier = np.select(
        [
            probability <= screening_threshold,
            probability <= referral_threshold,
        ],
        ["Lower Estimated Risk", "Moderate Estimated Risk"],
        default="Higher Estimated Risk",
    )
    tier_counts = {
        tier: int((predicted_tier == tier).sum())
        for tier in (
            "Lower Estimated Risk",
            "Moderate Estimated Risk",
            "Higher Estimated Risk",
        )
    }
    tier_confusion_matrix = {
        "rows": ["actual_negative", "actual_positive"],
        "columns": list(tier_counts),
        "values": [
            [
                int(((y_true == 0) & (predicted_tier == tier)).sum())
                for tier in tier_counts
            ],
            [
                int(((y_true == 1) & (predicted_tier == tier)).sum())
                for tier in tier_counts
            ],
        ],
    }
    tier_metric_rows = []
    for tier in tier_counts:
        tier_predicted = (predicted_tier == tier).astype(int)
        tn, fp, fn, tp = confusion_matrix(
            y_true, tier_predicted, labels=[0, 1]
        ).ravel()
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        tier_metric_rows.append({
            "tier": tier,
            "count": tier_counts[tier],
            "accuracy": round((tp + tn) / len(y_true), 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        })
    return {
        "tier_counts": tier_counts,
        "tier_confusion_matrix": tier_confusion_matrix,
        "tier_metrics": tier_metric_rows,
    }


def compute_ece(y_true, probability, n_bins=10):
    """Expected Calibration Error with signed calibration gap per bin."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    calibration_rows = []
    ece = 0.0

    for lower, upper in zip(bins[:-1], bins[1:]):
        mask = (
            (probability >= lower)
            & ((probability < upper) if upper < 1.0 else (probability <= upper))
        )
        count = int(mask.sum())
        if count == 0:
            calibration_rows.append({
                "probability_bucket": f"{lower:.1f}-{upper:.1f}",
                "predicted_probability": None,
                "observed_frequency": None,
                "count": 0,
                "calibration_gap": None,
                "flag": "no_data",
            })
            continue

        predicted_prob = float(probability[mask].mean())
        observed_freq = float(y_true[mask].mean())
        signed_gap = observed_freq - predicted_prob
        abs_gap = abs(signed_gap)
        ece += (count / len(y_true)) * abs_gap

        # Interpretation flags
        if abs_gap > 0.10 and count >= 30:
            if signed_gap > 0:
                flag = "under-confident"
            else:
                flag = "over-confident"
        else:
            flag = "ok"

        calibration_rows.append({
            "probability_bucket": f"{lower:.1f}-{upper:.1f}",
            "predicted_probability": round(predicted_prob, 4),
            "observed_frequency": round(observed_freq, 4),
            "count": count,
            "calibration_gap": round(signed_gap, 4),
            "flag": flag,
        })

    return round(ece, 4), calibration_rows


def calibration_interpretation(calibration_rows):
    """Summarize the direction and range of material calibration gaps."""
    flagged = [
        row for row in calibration_rows
        if row["count"] >= 30 and row["calibration_gap"] is not None
        and abs(row["calibration_gap"]) > 0.10
    ]
    if not flagged:
        return {
            "flag": "no_material_systematic_gap",
            "message": "No probability bucket with at least 30 cases differs by more than 0.10.",
            "ranges": [],
        }

    directions = {"under-confident" if row["calibration_gap"] > 0 else "over-confident" for row in flagged}
    direction = directions.pop() if len(directions) == 1 else "mixed"
    return {
        "flag": direction,
        "message": "Material calibration gap(s) detected in: " + ", ".join(
            row["probability_bucket"] for row in flagged
        ),
        "ranges": [row["probability_bucket"] for row in flagged],
    }


def subgroup_metrics(X_test, y_true, probability, threshold):
    """Calibration and recall by Age band, Sex, and BMI group."""
    rows = []

    # --- Age subgroups ---
    ages = X_test["Age"].values
    age_groups = [
        ("age_18_44", ages <= 5),
        ("age_45_59", (ages >= 6) & (ages <= 8)),
        ("age_60_plus", ages >= 9),
    ]

    # --- Sex subgroups ---
    sexes = X_test["Sex"].values
    sex_groups = [
        ("male", sexes == 1),
        ("female", sexes == 0),
    ]

    # --- BMI subgroups ---
    bmis = X_test["BMI"].values
    bmi_groups = [
        ("bmi_normal", bmis < 25),
        ("bmi_overweight", (bmis >= 25) & (bmis < 30)),
        ("bmi_obese", bmis >= 30),
    ]

    for label, mask in age_groups + sex_groups + bmi_groups:
        n = int(mask.sum())
        if n == 0:
            continue
        yt = y_true[mask]
        yp = probability[mask]
        predicted = (yp >= threshold).astype(int)

        actual_rate = float(yt.mean())
        mean_pred = float(yp.mean())
        cal_err = actual_rate - mean_pred

        tp = int(((predicted == 1) & (yt == 1)).sum())
        fn = int(((predicted == 0) & (yt == 1)).sum())
        tn = int(((predicted == 0) & (yt == 0)).sum())
        fp = int(((predicted == 1) & (yt == 0)).sum())
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        spec = tn / (tn + fp) if (tn + fp) else 0.0
        prec = tp / (tp + fp) if (tp + fp) else 0.0

        if n < 30:
            flag = "insufficient_data"
        elif abs(cal_err) > 0.10:
            flag = "warning"
        else:
            flag = "ok"

        rows.append({
            "subgroup": label,
            "n": n,
            "actual_positive_rate": round(actual_rate, 4),
            "mean_predicted": round(mean_pred, 4),
            "calibration_gap": round(cal_err, 4),
            "recall": round(recall, 4),
            "specificity": round(spec, 4),
            "precision": round(prec, 4),
            "flag": flag,
        })

    return rows


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def evaluate_all():
    # Load training summary for stored thresholds
    summary_path = os.path.join(MODEL_DIR, "training_summary.json")
    with open(summary_path) as f:
        training_summary = json.load(f)

    all_threshold_rows = []    # threshold_metrics.csv
    all_standard_rows = []     # standard_metrics.csv
    all_tier_rows = []         # risk_tier_metrics.csv
    all_calibration_rows = []  # calibration_table.csv
    all_subgroup_rows = []     # subgroup_metrics.csv
    evaluation_report = {}     # evaluation_report.json
    recommendation_lines = []  # threshold_recommendations.txt

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    axes = axes.flatten()

    for idx, (cat, config) in enumerate(TASKS.items()):
        print(f"\n{'='*70}")
        print(f"[EVALUATING] {cat.upper()} — {config['label']}")
        print(f"{'='*70}")

        # Reproduce deterministic split
        X, y, feature_subset, cohort_source = config["loader"]()
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y,
        )

        # Load saved model
        model_path = os.path.join(MODEL_DIR, f"{cat}_model.pkl")
        model = joblib.load(model_path)
        probability = model.predict_proba(X_test)[:, 1]
        y_test = np.asarray(y_test)

        # Stored thresholds
        info = training_summary[cat]
        screening_thresh = info["screening_threshold"]
        referral_thresh = info["referral_threshold"]

        # Discrimination
        auroc = round(roc_auc_score(y_test, probability), 4)
        pr_auc = round(average_precision_score(y_test, probability), 4)
        brier = round(brier_score_loss(y_test, probability), 4)
        ece, cal_rows = compute_ece(y_test, probability)

        print(f"  AUROC={auroc}  PR-AUC={pr_auc}  Brier={brier}  ECE={ece}")

        # ------------------------------------------------------------------
        # 1. Threshold sweep: 0.20–0.80 by 0.05 plus stored thresholds
        # ------------------------------------------------------------------
        sweep = sorted(set(
            [round(t, 4) for t in np.arange(0.20, 0.81, 0.05)]
            + [screening_thresh, referral_thresh]
        ))

        threshold_rows = []
        for t in sweep:
            row = threshold_metrics(y_test, probability, t)
            row["category"] = cat
            threshold_rows.append(row)
            all_threshold_rows.append(row)

        # Metrics at stored thresholds
        screen_row = threshold_metrics(y_test, probability, screening_thresh)
        referral_row = threshold_metrics(y_test, probability, referral_thresh)
        tier_summary = tier_metrics(
            y_test, probability, screening_thresh, referral_thresh
        )
        for tier_row in tier_summary["tier_metrics"]:
            all_tier_rows.append({"category": cat, **tier_row})
        for operating_point, row in (
            ("screening", screen_row),
            ("referral", referral_row),
        ):
            all_standard_rows.append({
                "category": cat,
                "operating_point": operating_point,
                **row,
            })

        # 2. Explicit high-tier recall (p > referral_threshold)
        high_tier_mask = probability > referral_thresh
        if high_tier_mask.sum() > 0 and y_test.sum() > 0:
            high_tier_tp = int(((probability > referral_thresh) & (y_test == 1)).sum())
            high_tier_recall = round(high_tier_tp / int(y_test.sum()), 4)
        else:
            high_tier_recall = 0.0
        high_tier_precision = referral_row["precision"]

        print(f"  Screening  (t={screening_thresh:.4f}): sens={screen_row['sensitivity']}, spec={screen_row['specificity']}, prec={screen_row['precision']}, f1={screen_row['f1']}")
        print(f"  Referral   (t={referral_thresh:.4f}): sens={referral_row['sensitivity']}, spec={referral_row['specificity']}, prec={referral_row['precision']}, f1={referral_row['f1']}")
        print(f"  High-tier recall (p > referral): {high_tier_recall}")

        # ------------------------------------------------------------------
        # 3. Calibration table
        # ------------------------------------------------------------------
        for cr in cal_rows:
            cr["category"] = cat
            all_calibration_rows.append(cr)

        # ------------------------------------------------------------------
        # 4. Subgroup metrics (at screening threshold)
        # ------------------------------------------------------------------
        sg_rows = subgroup_metrics(X_test, y_test, probability, screening_thresh)
        for sg in sg_rows:
            sg["category"] = cat
            sg["threshold_used"] = screening_thresh
            all_subgroup_rows.append(sg)

        subgroup_warnings = [sg for sg in sg_rows if sg["flag"] != "ok"]
        calibration_warnings = [
            cr for cr in cal_rows if cr["flag"] not in ("ok", "no_data")
        ]
        calibration_summary = calibration_interpretation(cal_rows)

        # ------------------------------------------------------------------
        # 5. Threshold recommendation: highest recall with precision ≥ 0.60
        # ------------------------------------------------------------------
        eligible = [row for row in threshold_rows if row["precision"] >= 0.60]
        recommended = (
            max(eligible, key=lambda row: (row["sensitivity"], row["threshold"]))
            if eligible
            else None
        )

        if recommended:
            rec_line = (
                f"{cat}: Recommended threshold = {recommended['threshold']:.4f} "
                f"(sensitivity={recommended['sensitivity']:.4f}, "
                f"specificity={recommended['specificity']:.4f}, "
                f"precision={recommended['precision']:.4f}, "
                f"f1={recommended['f1']:.4f})"
            )
        else:
            rec_line = (
                f"{cat}: No threshold in the sweep achieves precision >= 0.60. "
                f"Stored referral threshold {referral_thresh:.4f} has "
                f"precision={referral_row['precision']:.4f}."
            )
        recommendation_lines.append(rec_line)
        print(f"  Recommendation: {rec_line}")
        print(f"  Calibration: {calibration_summary['message']}")

        # ------------------------------------------------------------------
        # 6. Calibration plot
        # ------------------------------------------------------------------
        ax = axes[idx]
        populated_cal_rows = [cr for cr in cal_rows if cr["count"] > 0]
        pred_probs = [cr["predicted_probability"] for cr in populated_cal_rows]
        obs_freqs = [cr["observed_frequency"] for cr in populated_cal_rows]
        counts = [cr["count"] for cr in populated_cal_rows]

        ax.plot([0, 1], [0, 1], "k--", lw=1, label="Ideal")
        ax.plot(pred_probs, obs_freqs, "o-", color="#0d6efd", lw=2,
                label=f"Brier={brier:.3f}  ECE={ece:.3f}")
        # Size markers by bin count
        for px, py, c in zip(pred_probs, obs_freqs, counts):
            ax.scatter(px, py, s=max(20, min(c * 2, 200)), color="#0d6efd",
                       alpha=0.4, zorder=5)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.set_xlabel("Mean Predicted Probability")
        ax.set_ylabel("Observed Frequency")
        ax.set_title(f"{config['label']}\n(N={len(y_test)}, Prevalence={y_test.mean():.1%})",
                      fontsize=11, fontweight="bold")
        ax.legend(loc="lower right", fontsize=9)
        ax.grid(True, alpha=0.3)

        # ------------------------------------------------------------------
        # Build report entry
        # ------------------------------------------------------------------
        evaluation_report[cat] = {
            "label": config["label"],
            "cohort_source": cohort_source,
            "test_size": int(len(y_test)),
            "event_prevalence_pct": round(float(y_test.mean()) * 100, 1),
            "auroc": auroc,
            "pr_auc": pr_auc,
            "brier_score": brier,
            "ece": ece,
            "screening_threshold": screening_thresh,
            "referral_threshold": referral_thresh,
            "metrics_at_screening": screen_row,
            "metrics_at_referral": referral_row,
            "risk_tiers": tier_summary,
            "high_tier_recall": high_tier_recall,
            "high_tier_precision": high_tier_precision,
            "high_tier_operating_point": referral_row,
            "recommended_threshold": recommended,
            "recommendation_precision_floor": 0.60,
            "calibration_warnings": calibration_warnings,
            "calibration_interpretation": calibration_summary,
            "subgroup_warnings": subgroup_warnings,
            "model_status": info.get("model_status", "validated"),
            "calibration_quality": info.get("calibration_quality", "fair"),
            "uncertainty_level": info.get("uncertainty_level", "moderate"),
        }

    # ======================================================================
    # Write outputs
    # ======================================================================

    # threshold_metrics.csv
    tm_path = os.path.join(OUTPUT_DIR, "threshold_metrics.csv")
    with open(tm_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "category", "threshold", "accuracy", "sensitivity", "specificity",
            "precision", "f1", "tn", "fp", "fn", "tp",
        ])
        writer.writeheader()
        writer.writerows(all_threshold_rows)
    print(f"\n[SAVED] {tm_path}")

    # standard_metrics.csv
    sm_path = os.path.join(OUTPUT_DIR, "standard_metrics.csv")
    with open(sm_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "category", "operating_point", "threshold", "accuracy",
            "sensitivity", "specificity", "precision", "f1",
            "tn", "fp", "fn", "tp",
        ])
        writer.writeheader()
        writer.writerows(all_standard_rows)
    print(f"[SAVED] {sm_path}")

    # risk_tier_metrics.csv
    tier_path = os.path.join(OUTPUT_DIR, "risk_tier_metrics.csv")
    with open(tier_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "category", "tier", "count", "accuracy", "precision", "recall",
            "f1", "tn", "fp", "fn", "tp",
        ])
        writer.writeheader()
        writer.writerows(all_tier_rows)
    print(f"[SAVED] {tier_path}")

    # calibration_table.csv
    ct_path = os.path.join(OUTPUT_DIR, "calibration_table.csv")
    with open(ct_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "category", "probability_bucket", "predicted_probability",
            "observed_frequency", "count", "calibration_gap", "flag",
        ])
        writer.writeheader()
        writer.writerows(all_calibration_rows)
    print(f"[SAVED] {ct_path}")

    # subgroup_metrics.csv
    sg_path = os.path.join(OUTPUT_DIR, "subgroup_metrics.csv")
    with open(sg_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "category", "subgroup", "n", "actual_positive_rate",
            "mean_predicted", "calibration_gap", "recall", "specificity",
            "precision", "threshold_used", "flag",
        ])
        writer.writeheader()
        writer.writerows(all_subgroup_rows)
    print(f"[SAVED] {sg_path}")

    # calibration_curves.png
    fig.tight_layout(pad=3.0)
    plot_path = os.path.join(OUTPUT_DIR, "calibration_curves.png")
    fig.savefig(plot_path, dpi=200)
    plt.close(fig)
    print(f"[SAVED] {plot_path}")

    # evaluation_report.json
    report_path = os.path.join(OUTPUT_DIR, "evaluation_report.json")
    with open(report_path, "w") as f:
        json.dump(evaluation_report, f, indent=2)
    print(f"[SAVED] {report_path}")

    # threshold_recommendations.txt
    rec_path = os.path.join(OUTPUT_DIR, "threshold_recommendations.txt")
    with open(rec_path, "w") as f:
        f.write("Threshold Recommendations (highest high-risk recall with precision >= 0.60)\n")
        f.write("=" * 70 + "\n\n")
        for line in recommendation_lines:
            f.write(line + "\n")
        f.write("\n" + "=" * 70 + "\n")
        f.write("The production recommendation uses a precision floor of 0.60 and\n")
        f.write("maximizes sensitivity (high-risk recall) among eligible sweep points.\n")
        f.write("The referral operating point is the saved wrapper's current\n")
        f.write("Higher Estimated Risk classification threshold.\n")
        f.write("Note: Ground truth is binary for every cohort. The UI exposes three\n")
        f.write("probability tiers (Lower / Moderate / Higher Estimated Risk), but\n")
        f.write("recall is always calculated against the binary clinical endpoint.\n")
        f.write("High-tier recall is the fraction of true positives assigned the\n")
        f.write("Higher Estimated Risk tier (probability > referral_threshold).\n")
    print(f"[SAVED] {rec_path}")

    print(f"\n{'='*70}")
    print("[EVALUATION COMPLETE] All outputs written to evaluation_results/")
    print(f"{'='*70}\n")

    return evaluation_report


if __name__ == "__main__":
    evaluate_all()
