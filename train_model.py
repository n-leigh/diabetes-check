"""
train_model.py
Trains one classifier per complication category, each on its own
category-specific dataset (see build_datasets_2021_2024.py for why the
three categories now use different real respondent pools drawn from
2021-2024 BRFSS data, rather than one shared dataset).

For each category:
1. Load that category's dataset
2. Apply the clinical rule matrix to generate a Low/Moderate/High label
3. Train Decision Tree, Logistic Regression, and Random Forest, compare
   held-out accuracy, keep the best
4. Save the winning model plus a JSON summary of the comparison

Run: python3 train_model.py
"""

import os
import json
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib

from rule_matrix import (
    score_cardiovascular, score_neuropathy_mobility,
    score_general_complication_burden, classify_pct, RULE_VERSION,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Each category: (dataset file, scoring function, max possible score,
# feature columns this category's dataset actually has available)
CATEGORY_CONFIG = {
    "cardiovascular": {
        "dataset": "cardio_dataset.csv",
        "score_fn": score_cardiovascular,
        "max_score": 2 + 2 + 1 + 3 + 3 + 2 + 2,  # 15
        "features": ["HighBP", "HighChol", "Smoker", "HeartDiseaseorAttack", "Stroke",
                     "BMI", "Age", "PhysHlth", "GenHlth", "MentHlth", "NoDocbcCost", "Sex"],
    },
    "neuropathy_mobility": {
        "dataset": "neuropathy_dataset.csv",
        "score_fn": score_neuropathy_mobility,
        "max_score": 3 + 2 + 1 + 1,  # 7
        "features": ["Smoker", "HeartDiseaseorAttack", "Stroke", "BMI", "Age", "DiffWalk",
                     "PhysHlth", "GenHlth", "MentHlth", "NoDocbcCost", "Sex"],
    },
    "general_burden": {
        "dataset": "general_burden_dataset.csv",
        "score_fn": score_general_complication_burden,
        "max_score": 3 + 1 + 1,  # 5
        "features": ["Smoker", "HeartDiseaseorAttack", "Stroke", "BMI", "Age",
                     "PhysHlth", "GenHlth", "MentHlth", "NoDocbcCost", "Sex"],
    },
}

CANDIDATE_MODELS = {
    "Decision Tree": lambda: DecisionTreeClassifier(max_depth=5, random_state=42),
    "Logistic Regression": lambda: make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=2000, random_state=42)
    ),
    "Random Forest": lambda: RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42),
}


def label_dataset(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    scores = df.apply(lambda row: config["score_fn"](row.to_dict()), axis=1)
    pct = (scores / config["max_score"] * 100).round().clip(upper=100)
    df = df.copy()
    df["label"] = pct.apply(classify_pct)
    return df


def train_and_evaluate():
    summary = {}

    for category, config in CATEGORY_CONFIG.items():
        path = os.path.join(BASE_DIR, "data", config["dataset"])
        df = pd.read_csv(path)
        df = label_dataset(df, config)

        print(f"\n{'='*60}\n{category.upper()}  (n={len(df)}, source: {config['dataset']})\n{'='*60}")
        print(df["label"].value_counts())

        X = df[config["features"]]
        y = df["label"]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        results = {}
        for name, build in CANDIDATE_MODELS.items():
            clf = build()
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)
            acc = accuracy_score(y_test, y_pred)
            results[name] = {"model": clf, "accuracy": acc, "y_pred": y_pred}
            print(f"  {name:22s} accuracy: {acc:.4f}")

        best_name = max(results, key=lambda n: results[n]["accuracy"])
        best = results[best_name]
        print(f"\n  --> Best model for {category}: {best_name} ({best['accuracy']:.4f})\n")
        print(classification_report(y_test, best["y_pred"], zero_division=0))
        print("Confusion matrix (rows=actual, cols=predicted, order Low/Moderate/High):")
        print(confusion_matrix(y_test, best["y_pred"], labels=["Low", "Moderate", "High"]))

        joblib.dump(best["model"], os.path.join(BASE_DIR, "model", f"{category}_model.pkl"))
        summary[category] = {
            "best_model": best_name,
            "accuracy": round(best["accuracy"], 4),
            "all_models_compared": {n: round(r["accuracy"], 4) for n, r in results.items()},
            "features": config["features"],
            "dataset": config["dataset"],
            "n_respondents": len(df),
            "rule_matrix_version": RULE_VERSION,
        }

    with open(os.path.join(BASE_DIR, "model", "training_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print("\nSaved best models to model/*.pkl")
    print("Saved comparison summary to model/training_summary.json")
    return summary


if __name__ == "__main__":
    train_and_evaluate()
