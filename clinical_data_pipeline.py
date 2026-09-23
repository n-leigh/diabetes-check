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
    Extracts and standardizes the diabetic retinopathy cohort by pooling all
    available NHANES retinal photography exam cycles:
      - 2005-2006 (OPXRET_D): ~543 diabetic participants with retinal exam
      - 2007-2008 (OPXRET_E): ~820 diabetic participants with retinal exam
      (2003-2004 OPXRET_C is not available on CDC servers — HTTP 404)

    For each cycle, the following files are merged:
      - OPXRET_*: Digital retinal photography grades (OPDURET, OPDDRET)
      - DIQ_*:    Diabetes diagnosis + doctor-reported retinopathy (DIQ010, DIQ080)
      - DEMO_*:   Age, sex
      - BMX_*:    BMI
      - BPQ_*:    High BP, high cholesterol
      - SMQ_*:    Smoking history
      - VIQ_*:    Blurry vision symptom (VIQ071)
      - GHB_*:    HbA1c glycohemoglobin lab (LBXGH) — the #1 ADA retinopathy predictor

    Each cycle's raw XPT files are cached in their own subdirectory under raw_dir
    (e.g. raw_retinopathy/2005-2006/) to prevent filename collisions between cycles.
    Files that already exist on disk are never re-downloaded.
    """
    import urllib.request

    if raw_dir is None:
        raw_dir = os.environ.get("NHANES_RETINOPATHY_DIR", os.path.join(DATA_DIR, "raw_retinopathy"))

    os.makedirs(raw_dir, exist_ok=True)

    # ── CDC NHANES cycles with retinal photography data ────────────────────────
    # 2003-2004 (OPXRET_C) is excluded: CDC returns HTTP 404 for that file.
    NHANES_CYCLES = [
        {
            "label": "2005-2006",
            "suffix": "D",
            "year": "2005",
            "files": {
                "opx":  "OPXRET_D.xpt",
                "diq":  "DIQ_D.xpt",
                "demo": "DEMO_D.xpt",
                "bmx":  "BMX_D.xpt",
                "bpq":  "BPQ_D.xpt",
                "smq":  "SMQ_D.xpt",
                "viq":  "VIQ_D.xpt",
                "ghb":  "GHB_D.xpt",
            },
        },
        {
            "label": "2007-2008",
            "suffix": "E",
            "year": "2007",
            "files": {
                "opx":  "OPXRET_E.xpt",
                "diq":  "DIQ_E.xpt",
                "demo": "DEMO_E.xpt",
                "bmx":  "BMX_E.xpt",
                "bpq":  "BPQ_E.xpt",
                "smq":  "SMQ_E.xpt",
                "viq":  "VIQ_E.xpt",
                "ghb":  "GHB_E.xpt",
            },
        },
    ]

    def get_xpt(cycle_dir, filename, url):
        """Download XPT to cycle-specific subdir; return as DataFrame.
        Falls back to flat raw_dir for backwards compatibility with any
        files the user may have pre-downloaded there."""
        os.makedirs(cycle_dir, exist_ok=True)
        local_path = os.path.join(cycle_dir, filename)
        # Backwards-compat: also check the flat raw_dir (original pipeline behaviour)
        flat_path = os.path.join(raw_dir, filename)
        if os.path.exists(local_path):
            pass  # already in cycle subdir
        elif os.path.exists(flat_path):
            local_path = flat_path  # use pre-existing flat file, don't re-download
        else:
            print(f"[Retinopathy Pipeline] Downloading {filename} from CDC...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(local_path, "wb") as f:
                f.write(resp.read())
        return pd.read_sas(local_path)

    def process_cycle(cycle):
        """Download, merge, and clean one NHANES retinopathy cycle."""
        label = cycle["label"]
        year  = cycle["year"]
        fs    = cycle["files"]
        base  = f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles"
        cdir  = os.path.join(raw_dir, label)   # e.g. raw_retinopathy/2005-2006/

        print(f"[Retinopathy Pipeline] Processing cycle {label}...")

        df_diq  = get_xpt(cdir, fs["diq"],  f"{base}/{fs['diq']}")
        df_opx  = get_xpt(cdir, fs["opx"],  f"{base}/{fs['opx']}")
        df_demo = get_xpt(cdir, fs["demo"], f"{base}/{fs['demo']}")
        df_bmx  = get_xpt(cdir, fs["bmx"],  f"{base}/{fs['bmx']}")
        df_bpq  = get_xpt(cdir, fs["bpq"],  f"{base}/{fs['bpq']}")
        df_smq  = get_xpt(cdir, fs["smq"],  f"{base}/{fs['smq']}")
        df_viq  = get_xpt(cdir, fs["viq"],  f"{base}/{fs['viq']}")
        df_ghb  = get_xpt(cdir, fs["ghb"],  f"{base}/{fs['ghb']}")

        # Diabetic cohort filter: told diabetes, on insulin, or on diabetes pills
        diab_mask = (
            (df_diq["DIQ010"] == 1.0) |
            (df_diq["DIQ050"] == 1.0) |
            (df_diq["DID070"] == 1.0)
        )
        m = df_diq[diab_mask][["SEQN", "DID040", "DIQ080"]].merge(
            df_demo[["SEQN", "RIDAGEYR", "RIAGENDR"]], on="SEQN", how="inner"
        ).merge(df_bmx[["SEQN", "BMXBMI"]],         on="SEQN", how="left"
        ).merge(df_bpq[["SEQN", "BPQ020", "BPQ080"]], on="SEQN", how="left"
        ).merge(df_smq[["SEQN", "SMQ020"]],           on="SEQN", how="left"
        ).merge(df_viq[["SEQN", "VIQ071"]],           on="SEQN", how="left"
        ).merge(df_ghb[["SEQN", "LBXGH"]],            on="SEQN", how="left"
        ).merge(df_opx[["SEQN", "OPDURET", "OPDDRET"]], on="SEQN", how="left")

        # Retinopathy label from retinal photography + self-report
        def get_target(row):
            u, d, told = row["OPDURET"], row["OPDDRET"], row["DIQ080"]
            if (pd.notna(u) and u > 10.0) or (pd.notna(d) and d > 10.0) or (told == 1.0):
                return 1
            if (pd.notna(u) and u == 10.0) or (pd.notna(d) and d == 10.0) or (told == 2.0):
                return 0
            return np.nan

        m["target"] = m.apply(get_target, axis=1)
        clean = m.dropna(subset=["target"]).copy()

        # Standardize features
        clean["age"]       = clean["RIDAGEYR"]
        clean["sex"]       = clean["RIAGENDR"].apply(lambda s: 1 if s == 1.0 else 0)
        clean["bmi"]       = clean["BMXBMI"].fillna(clean["BMXBMI"].median()).round(1)
        clean["high_bp"]   = clean["BPQ020"].apply(lambda b: 1 if b == 1.0 else 0)
        clean["high_chol"] = clean["BPQ080"].apply(lambda c: 1 if c == 1.0 else 0)
        clean["smoker"]    = clean["SMQ020"].apply(lambda s: 1 if s == 1.0 else 0)
        clean["blurry_vision"] = clean["VIQ071"].apply(lambda v: 1 if v == 1.0 else 0)

        # Diabetes duration: age minus age-at-diagnosis; impute missing as 5 yrs
        dur = clean["RIDAGEYR"] - clean["DID040"]
        clean["diabetes_duration_years"] = dur.apply(
            lambda d: max(0.0, float(d)) if (pd.notna(d) and 0 <= d <= 80) else 5.0
        ).round(1)

        # HbA1c (LBXGH, %): impute missing with cohort median
        ghb_median = clean["LBXGH"].median()
        clean["hba1c"] = clean["LBXGH"].fillna(ghb_median).round(1)

        clean["target_retinopathy"] = clean["target"].astype(int)
        clean["_cycle"] = label   # internal marker, dropped before saving

        print(f"                       {label}: {len(clean)} usable records "
              f"(retinopathy prevalence: "
              f"{clean['target_retinopathy'].mean():.1%})")
        return clean

    # ── Process and pool all cycles ───────────────────────────────────────────
    cycle_dfs = []
    for cycle in NHANES_CYCLES:
        try:
            cycle_dfs.append(process_cycle(cycle))
        except Exception as exc:
            print(f"[Retinopathy Pipeline] WARNING: Skipping cycle {cycle['label']}: {exc}")

    if not cycle_dfs:
        raise RuntimeError("No retinopathy cycles could be processed.")

    pooled = pd.concat(cycle_dfs, ignore_index=True)

    # Verify no duplicate SEQNs crept in (safety net)
    seqn_col = "SEQN" if "SEQN" in pooled.columns else None
    if seqn_col and pooled[seqn_col].duplicated().any():
        dupes = pooled[seqn_col].duplicated().sum()
        print(f"[Retinopathy Pipeline] WARNING: {dupes} duplicate SEQNs detected — deduplicating.")
        pooled = pooled.drop_duplicates(subset=[seqn_col])

    out_cols = [
        "age", "sex", "bmi", "high_bp", "high_chol", "smoker",
        "diabetes_duration_years", "blurry_vision", "hba1c", "target_retinopathy",
    ]
    clean_df = pooled[out_cols].copy()

    out_path = os.path.join(DATA_DIR, "processed_retinopathy_cohort.csv")
    clean_df.to_csv(out_path, index=False)

    print(f"\n[Retinopathy Pipeline] Saved pooled Retinopathy cohort to {out_path}")
    print(f"                       Total rows     : {len(clean_df):,}")
    print(f"                       Cycles pooled  : {[c['label'] for c in NHANES_CYCLES]}")
    print(f"                       HbA1c coverage : {clean_df['hba1c'].notna().mean():.1%}")
    print(f"                       Target prevalence: "
          f"{clean_df['target_retinopathy'].value_counts(normalize=True).to_dict()}\n")
    return clean_df


if __name__ == "__main__":
    build_cardiovascular_cohort()
    build_nephropathy_cohort()
    build_retinopathy_cohort()
