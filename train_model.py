"""
train_model.py
1. Loads data/diabetes_dataset.csv
2. Applies the clinical rule matrix (rule_matrix.py) to generate a
   Low/Moderate/High label for each of the 3 complication categories
3. Trains THREE classifiers per category (Decision Tree, Logistic
   Regression, Random Forest), compares them on held-out accuracy, and
   keeps the best-performing model per category
4. Prints a comparison table + full evaluation metrics for the winner,
   and saves the winning models to model/, plus a JSON summary of which
   algorithm won and why (useful straight in your results chapter)

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

from rule_matrix import compute_all_risks

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FEATURE_COLUMNS = [
    "HighBP", "HighChol", "Smoker", "HeartDiseaseorAttack", "Stroke",
    "BMI", "Age", "DiffWalk", "PhysHlth", "GenHlth", "MentHlth",
    "NoDocbcCost", "Sex",
]

CATEGORIES = ["cardiovascular", "neuropathy_mobility", "general_burden"]

CANDIDATE_MODELS = {
    "Decision Tree": lambda: DecisionTreeClassifier(max_depth=5, random_state=42),
    "Logistic Regression": lambda: make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=2000, random_state=42)
    ),
    "Random Forest": lambda: RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42),
}


def load_and_label(path=None):
    if path is None:
        path = os.path.join(BASE_DIR, "data", "diabetes_dataset.csv")
    df = pd.read_csv(path)
    labels = {cat: [] for cat in CATEGORIES}
    for _, row in df.iterrows():
        risks = compute_all_risks(row.to_dict())
        for cat in CATEGORIES:
            labels[cat].append(risks[cat]["label"])
    for cat in CATEGORIES:
        df[f"label_{cat}"] = labels[cat]
    return df


def train_and_evaluate(df):
    X = df[FEATURE_COLUMNS]
    summary = {}

    for cat in CATEGORIES:
        y = df[f"label_{cat}"]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        print(f"\n{'='*60}\n{cat.upper()}\n{'='*60}")
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
        print(f"\n  --> Best model for {cat}: {best_name} ({best['accuracy']:.4f})\n")
        print(classification_report(y_test, best["y_pred"], zero_division=0))
        print("Confusion matrix (rows=actual, cols=predicted):")
        print(confusion_matrix(y_test, best["y_pred"], labels=["Low", "Moderate", "High"]))

        joblib.dump(best["model"], os.path.join(BASE_DIR, "model", f"{cat}_model.pkl"))
        summary[cat] = {
            "best_model": best_name,
            "accuracy": round(best["accuracy"], 4),
            "all_models_compared": {n: round(r["accuracy"], 4) for n, r in results.items()},
        }

    with open(os.path.join(BASE_DIR, "model", "training_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print("\nSaved best models to model/*.pkl")
    print("Saved comparison summary to model/training_summary.json")
    return summary


if __name__ == "__main__":
    df = load_and_label()
    print(f"Loaded {len(df)} rows.")
    print(df[[f"label_{c}" for c in CATEGORIES]].apply(pd.Series.value_counts))
    train_and_evaluate(df)
