"""
generate_sample_data.py
Creates a small synthetic CSV matching the CDC Diabetes Health Indicators
schema, ONLY so your team can test the training pipeline and Flask app
before downloading the real dataset. Replace data/diabetes_dataset.csv
with the real Kaggle export once you have it — same column names, so
nothing else needs to change.

Real dataset: search Kaggle for "CDC Diabetes Health Indicators" (BRFSS).
Filter to Diabetes_binary == 1 (or Diabetes_012 in {1,2} depending on
which version you grab) before use, since this case study is about
complications in people who already have diabetes.
"""

import numpy as np
import pandas as pd

np.random.seed(42)
N = 400  # comfortably inside your 300-500 requirement

df = pd.DataFrame({
    "HighBP": np.random.binomial(1, 0.55, N),
    "HighChol": np.random.binomial(1, 0.5, N),
    "Smoker": np.random.binomial(1, 0.35, N),
    "HeartDiseaseorAttack": np.random.binomial(1, 0.2, N),
    "Stroke": np.random.binomial(1, 0.08, N),
    "BMI": np.random.normal(30, 6, N).clip(15, 55).round(1),
    "Age": np.random.randint(1, 14, N),          # BRFSS age band code
    "DiffWalk": np.random.binomial(1, 0.3, N),
    "PhysHlth": np.random.randint(0, 31, N),      # days of poor physical health
    "GenHlth": np.random.randint(1, 6, N),        # 1=excellent .. 5=poor
    "MentHlth": np.random.randint(0, 31, N),
    "NoDocbcCost": np.random.binomial(1, 0.15, N),
    "Sex": np.random.binomial(1, 0.5, N),
})

df.to_csv("/home/claude/diabetes_project/data/diabetes_dataset.csv", index=False)
print(f"Wrote {len(df)} synthetic rows to data/diabetes_dataset.csv")
