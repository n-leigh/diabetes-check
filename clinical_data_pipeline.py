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


def build_retinopathy_cohort(raw_dir=None):
    """
    Extracts and standardizes the diabetic retinopathy cohort from CDC NHANES 2007-2008:
    - OPXRET_E: Digital retinal photography exam (OPDURET, OPDDRET).
    - DIQ_E: Diabetes diagnosis and doctor-diagnosed retinopathy.
    - DEMO_E, BMX_E, BPQ_E, SMQ_E, VIQ_E: Demographic, biometric, cardiovascular, and visual symptoms.
    """
    import urllib.request

    if raw_dir is None:
        raw_dir = os.environ.get("NHANES_RETINOPATHY_DIR", os.path.join(DATA_DIR, "raw_retinopathy"))

    os.makedirs(raw_dir, exist_ok=True)

    def get_xpt(filename, url):
        local_path = os.path.join(raw_dir, filename)
        sub_path = os.path.join(raw_dir, "2007-2008", filename)
        if os.path.exists(sub_path):
            local_path = sub_path
        elif not os.path.exists(local_path):
            print(f"[Retinopathy Pipeline] Downloading {filename} from CDC...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(local_path, "wb") as f:
                f.write(resp.read())
        return pd.read_sas(local_path)

    df_diq = get_xpt("DIQ_E.xpt", "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/DIQ_E.xpt")
    df_opx = get_xpt("OPXRET_E.xpt", "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/OPXRET_E.xpt")
    df_demo = get_xpt("DEMO_E.xpt", "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/DEMO_E.xpt")
    df_bmx = get_xpt("BMX_E.xpt", "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/BMX_E.xpt")
    df_bpq = get_xpt("BPQ_E.xpt", "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/BPQ_E.xpt")
    df_smq = get_xpt("SMQ_E.xpt", "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/SMQ_E.xpt")
    df_viq = get_xpt("VIQ_E.xpt", "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/VIQ_E.xpt")

    diab_mask = (df_diq["DIQ010"] == 1.0) | (df_diq["DIQ050"] == 1.0) | (df_diq["DID070"] == 1.0)
    m = df_diq[diab_mask][["SEQN", "DID040", "DIQ080"]].merge(
        df_demo[["SEQN", "RIDAGEYR", "RIAGENDR"]], on="SEQN", how="inner"
    ).merge(df_bmx[["SEQN", "BMXBMI"]], on="SEQN", how="left"
    ).merge(df_bpq[["SEQN", "BPQ020", "BPQ080"]], on="SEQN", how="left"
    ).merge(df_smq[["SEQN", "SMQ020", "SMQ040"]], on="SEQN", how="left"
    ).merge(df_viq[["SEQN", "VIQ071"]], on="SEQN", how="left"
    ).merge(df_opx[["SEQN", "OPDURET", "OPDDRET"]], on="SEQN", how="left")

    def get_target(row):
        u, d, told = row["OPDURET"], row["OPDDRET"], row["DIQ080"]
        if (pd.notna(u) and u > 10.0) or (pd.notna(d) and d > 10.0) or (told == 1.0):
            return 1
        if (pd.notna(u) and u == 10.0) or (pd.notna(d) and d == 10.0) or (told == 2.0):
            return 0
        return np.nan

    m["target"] = m.apply(get_target, axis=1)
    clean = m.dropna(subset=["target"]).copy()

    clean["age"] = clean["RIDAGEYR"]
    clean["sex"] = clean["RIAGENDR"].apply(lambda s: 1 if s == 1.0 else 0)
    clean["bmi"] = clean["BMXBMI"].fillna(clean["BMXBMI"].median()).round(1)
    clean["high_bp"] = clean["BPQ020"].apply(lambda b: 1 if b == 1.0 else 0)
    clean["high_chol"] = clean["BPQ080"].apply(lambda c: 1 if c == 1.0 else 0)
    clean["smoker"] = clean["SMQ020"].apply(lambda s: 1 if s == 1.0 else 0)

    dur = clean["RIDAGEYR"] - clean["DID040"]
    clean["diabetes_duration_years"] = dur.apply(lambda d: max(0.0, float(d)) if (pd.notna(d) and 0 <= d <= 80) else 5.0).round(1)
    clean["blurry_vision"] = clean["VIQ071"].apply(lambda v: 1 if v == 1.0 else 0)
    clean["target_retinopathy"] = clean["target"].astype(int)

    out_cols = ["age", "sex", "bmi", "high_bp", "high_chol", "smoker", "diabetes_duration_years", "blurry_vision", "target_retinopathy"]
    clean_df = clean[out_cols]

    out_path = os.path.join(DATA_DIR, "processed_retinopathy_cohort.csv")
    clean_df.to_csv(out_path, index=False)
    print(f"[Retinopathy Pipeline] Saved cleaned Retinopathy cohort to {out_path}")
    print(f"                       Cohort size: {len(clean_df)}")
    print(f"                       Target prevalence: {clean_df['target_retinopathy'].value_counts(normalize=True).to_dict()}\n")
    return clean_df


if __name__ == "__main__":
    build_cardiovascular_cohort()
    build_nephropathy_cohort()
    build_retinopathy_cohort()
