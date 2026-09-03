"""
clinical_data_pipeline.py
Extracts and standardizes diabetic patient cohorts from CDC NHANES datasets:
1. Cardiovascular Cohort (NHANES 2017-2018): Predicts diagnosed coronary heart disease / MI / angina.
2. Nephropathy Cohort (NHANES 2021-2023): Predicts Chronic Kidney Disease presence and KDIGO staging.
"""

import os
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def build_cardiovascular_cohort():
    raw_path = os.path.join(DATA_DIR, "nhanes_2017_2018_heart_disease_prediction.csv")
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"Missing raw file: {raw_path}")

    df = pd.read_csv(raw_path)
    print(f"[CVD Pipeline] Loaded raw NHANES CVD dataset: {df.shape[0]} rows, {df.shape[1]} columns")

    # Cohort selection: confirmed diabetic patients
    diab_mask = (df["diabetes"] == 1.0) | (df["taking_insulin"] == 1.0) | (df["taking_diabetes_pills"] == 1.0)
    df_diab = df[diab_mask].copy()
    print(f"[CVD Pipeline] Filtered to confirmed diabetic cohort: {len(df_diab)} patients")

    # Feature standardization
    # NHANES sex: 1 = Male, 2 = Female -> convert to 1 = Male, 0 = Female
    sex_binary = df_diab["sex"].apply(lambda s: 1 if s == 1 else 0)
    
    # Smoking: current smoker or ever smoked
    smoker_flag = ((df_diab["smoking_current"] == 1.0) | (df_diab["smoking_ever"] == 1.0)).astype(int)

    # High BP: reported hypertension or taking BP meds
    high_bp_flag = ((df_diab["hypertension"] == 1.0) | (df_diab["taking_bp_meds"] == 1.0)).astype(int)

    # High Chol: reported high cholesterol or taking cholesterol meds
    high_chol_flag = ((df_diab["high_cholesterol"] == 1.0) | (df_diab["taking_cholesterol_meds"] == 1.0)).astype(int)

    clean_df = pd.DataFrame({
        "age": df_diab["age"].fillna(df_diab["age"].median()),
        "sex": sex_binary,
        "high_bp": high_bp_flag,
        "high_chol": high_chol_flag,
        "smoker": smoker_flag,
        "prior_stroke": df_diab["told_stroke"].fillna(0).astype(int),
        "family_history": df_diab["family_history_heart_attack"].fillna(0).astype(int),
        "physically_active": df_diab["physically_active"].fillna(1).astype(int),
        "taking_insulin": df_diab["taking_insulin"].fillna(0).astype(int),
        "target_heart_disease": df_diab["heart_disease"].fillna(0).astype(int)
    })

    out_path = os.path.join(DATA_DIR, "processed_cardiovascular_cohort.csv")
    clean_df.to_csv(out_path, index=False)
    print(f"[CVD Pipeline] Saved cleaned CVD cohort to {out_path}")
    print(f"               Target prevalence: {clean_df['target_heart_disease'].value_counts(normalize=True).to_dict()}\n")
    return clean_df


def build_nephropathy_cohort():
    raw_path = os.path.join(DATA_DIR, "CKD_NHANES_2021_2023.csv")
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"Missing raw file: {raw_path}")

    df = pd.read_csv(raw_path)
    print(f"[Nephrology Pipeline] Loaded raw NHANES CKD dataset: {df.shape[0]} rows, {df.shape[1]} columns")

    # Cohort selection: confirmed diabetic patients
    diab_mask = (df["diabetes_diagnosed"] == 1.0) | (df["insulin_use"] == 1.0) | (df["diabetes_pills"] == 1.0)
    df_diab = df[diab_mask].copy()

    # Filter out records where CKD staging is Unknown (missing laboratory results)
    known_mask = df_diab["ckd_stage"].notna() & (df_diab["ckd_stage"] != "Unknown")
    df_known = df_diab[known_mask].copy()
    print(f"[Nephrology Pipeline] Filtered to diabetic cohort with laboratory CKD staging: {len(df_known)} patients")

    # Standardize sex: 'Male' -> 1, 'Female' -> 0
    sex_binary = df_known["gender"].apply(lambda g: 1 if str(g).strip().lower() == "male" else 0)

    # Standardize smoking
    smoker_flag = df_known["ever_smoked"].apply(lambda s: 1 if s == 1.0 else 0)

    # High BP flag from systolic/diastolic or systolic >= 130 / diastolic >= 80 (AHA hypertension definition)
    bp_sys = df_known["bp_systolic"].fillna(df_known["bp_systolic"].median())
    bp_dia = df_known["bp_diastolic"].fillna(df_known["bp_diastolic"].median())
    high_bp_flag = ((bp_sys >= 130) | (bp_dia >= 80)).astype(int)

    # BMI
    bmi = df_known["bmi"].fillna(df_known["bmi"].median())

    # Target: CKD Presence (Stage 1-5 vs No CKD)
    # 0 = No CKD (normal eGFR and normal uACR)
    # 1 = Diagnosed CKD (KDIGO Stage 1, 2, 3a, 3b, 4, or 5)
    target_ckd = df_known["ckd_stage"].apply(lambda s: 0 if s == "No CKD" else 1)

    # KDIGO Clinical Risk Tier:
    # Low: No CKD
    # Moderate: Stage 1 (damage with normal eGFR) or Stage 2 (mildly decreased eGFR 60-89)
    # High: Stage 3a+ (eGFR < 60 mL/min/1.73m^2: Moderate-Severe to Kidney Failure)
    def map_kdigo_tier(stage):
        if stage == "No CKD":
            return "Low"
        elif "Stage 1" in stage or "Stage 2" in stage:
            return "Moderate"
        else:
            return "High"

    kdigo_tier = df_known["ckd_stage"].apply(map_kdigo_tier)

    clean_df = pd.DataFrame({
        "age": df_known["age"].fillna(df_known["age"].median()),
        "sex": sex_binary,
        "bmi": bmi,
        "bp_systolic": bp_sys,
        "bp_diastolic": bp_dia,
        "high_bp": high_bp_flag,
        "smoker": smoker_flag,
        "serum_creatinine": df_known["serum_creatinine"].fillna(df_known["serum_creatinine"].median()),
        "egfr": df_known["egfr"].fillna(df_known["egfr"].median()),
        "uacr": df_known["albumin_creatinine_ratio"].fillna(df_known["albumin_creatinine_ratio"].median()),
        "target_ckd_present": target_ckd,
        "target_kdigo_tier": kdigo_tier
    })

    out_path = os.path.join(DATA_DIR, "processed_nephropathy_cohort.csv")
    clean_df.to_csv(out_path, index=False)
    print(f"[Nephrology Pipeline] Saved cleaned Nephropathy cohort to {out_path}")
    print(f"                      Target CKD presence: {clean_df['target_ckd_present'].value_counts(normalize=True).to_dict()}")
    print(f"                      KDIGO Risk Tiers: {clean_df['target_kdigo_tier'].value_counts(normalize=True).to_dict()}\n")
    return clean_df


if __name__ == "__main__":
    build_cardiovascular_cohort()
    build_nephropathy_cohort()
