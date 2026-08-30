"""
build_datasets_2021_2024.py

Rebuilds the training data using 2021-2024 BRFSS data instead of the
original 2015 data, working around a real constraint: no single recent
year (or combination of years) contains every variable the original
rule matrix depends on. BRFSS rotates some questions between a core and
an optional module from year to year, and this affects two variables
specifically.

High blood pressure and high cholesterol ("ever told you have this")
were asked in 2021 and 2023, but not in 2022 or 2024.

Difficulty walking / climbing stairs was not asked in ANY of the
2021-2024 "clean" extracts provided, but IS present in the separate raw
2024 BRFSS file (301 raw columns, not pre-cleaned).

Since BRFSS surveys a different, anonymous set of people every year,
there is no valid way to attach one year's respondent answer onto a
different year's respondent record. Doing so would fabricate data that
was never actually collected from the same person. The only
methodologically sound option is to let each complication category
train on whichever real, internally-consistent respondent pool actually
has the variables that category's rule matrix needs.

This produces three separate datasets:

- cardio_dataset.csv        <- 2021 + 2023 (has HighBP, HighChol)
- general_burden_dataset.csv <- 2021 + 2022 + 2023 + 2024 (doesn't need
                                 HighBP/HighChol/DiffWalk, so all 4 years
                                 of real respondents can be used)
- neuropathy_dataset.csv    <- raw 2024 BRFSS only (has DiffWalk)

All three are filtered to diabetic-positive respondents only, matching
the original 2015-based approach.
"""

import pandas as pd
import numpy as np

DATA_DIR = "data_2024_update"

AGE_GROUP_TO_BAND = {
    "18 to 24": 1, "25 to 29": 2, "30 to 34": 3, "35 to 39": 4, "40 to 44": 5,
    "45 to 49": 6, "50 to 54": 7, "55 to 59": 8, "60 to 64": 9, "65 to 69": 10,
    "70 to 74": 11, "75 to 79": 12, "80 or older": 13,
}

GENHLTH_TO_NUM = {"Excellent": 1, "Very Good": 2, "Good": 3, "Fair": 4, "Poor": 5}


def load_clean_year(year: int) -> pd.DataFrame:
    df = pd.read_parquet(f"{DATA_DIR}/DATASET_{year}.parquet")
    df = df[df["diabetes"] == "Diabetic"].copy()

    out = pd.DataFrame()
    out["Sex"] = (df["sex_00"] == "Male").astype(int)
    out["Age"] = df["age_group_00"].map(AGE_GROUP_TO_BAND)
    out["BMI"] = df["bmi_00"]
    out["GenHlth"] = df["general_health_00"].map(GENHLTH_TO_NUM)
    out["PhysHlth"] = df["physical_health_days_00"]
    out["MentHlth"] = df["mental_health_days_00"]
    out["Smoker"] = df["smoked_100_cigarettes_00"]
    out["Stroke"] = df["had_stroke_00"]
    out["HeartDiseaseorAttack"] = df["had_heart_attack_00"] | df["had_coronary_heart_disease_00"]
    out["NoDocbcCost"] = df["cost_barrier_00"]

    if "high_bp_00" in df.columns:
        out["HighBP"] = df["high_bp_00"].map({"Yes": True, "Borderline": False, "No": False})
        out["HighChol"] = df["high_cholesterol_00"]

    out["source_year"] = year

    # drop rows missing any field we need, THEN cast booleans to clean 0/1 ints
    out = out.dropna()
    bool_cols = ["Smoker", "Stroke", "HeartDiseaseorAttack", "NoDocbcCost"]
    if "HighBP" in out.columns:
        bool_cols += ["HighBP", "HighChol"]
    for c in bool_cols:
        out[c] = out[c].astype(int)

    # drop implausible self-reported BMI values (a small fraction of survey
    # data always has data-entry errors at the extremes)
    out = out[(out["BMI"] >= 12) & (out["BMI"] <= 80)]

    return out


def build_cardio_dataset():
    df = pd.concat([load_clean_year(2021), load_clean_year(2023)], ignore_index=True)
    cols = ["HighBP", "HighChol", "Smoker", "HeartDiseaseorAttack", "Stroke",
            "BMI", "Age", "PhysHlth", "GenHlth", "MentHlth", "NoDocbcCost", "Sex", "source_year"]
    df = df[cols]
    df.to_csv("data/cardio_dataset.csv", index=False)
    print(f"cardio_dataset.csv: {len(df)} rows (2021+2023 diabetic-positive respondents)")
    return df


def build_general_burden_dataset():
    frames = [load_clean_year(y) for y in (2021, 2022, 2023, 2024)]
    df = pd.concat(frames, ignore_index=True)
    cols = ["Smoker", "HeartDiseaseorAttack", "Stroke", "BMI", "Age",
            "PhysHlth", "GenHlth", "MentHlth", "NoDocbcCost", "Sex", "source_year"]
    df = df[cols]
    df.to_csv("data/general_burden_dataset.csv", index=False)
    print(f"general_burden_dataset.csv: {len(df)} rows (2021-2024 diabetic-positive respondents)")
    return df


def build_neuropathy_dataset():
    usecols = ["DIABETE4", "_SEX", "_AGEG5YR", "_BMI5", "GENHLTH", "PHYSHLTH",
               "MENTHLTH", "DIFFWALK", "SMOKE100", "CVDSTRK3", "CVDINFR4",
               "CVDCRHD4", "MEDCOST1"]
    df = pd.read_csv(f"{DATA_DIR}/raw_2024_brfss.csv", usecols=usecols)
    df = df[df["DIABETE4"] == 1].copy()

    def clean_yesno(series):
        # BRFSS: 1=Yes, 2=No, 7=Don't know, 9=Refused -> keep only 1/2
        s = series.where(series.isin([1, 2]))
        return (s == 1).astype("Int64")

    out = pd.DataFrame()
    out["Sex"] = (df["_SEX"] == 1).astype(int)
    out["Age"] = df["_AGEG5YR"].where(df["_AGEG5YR"].between(1, 13))
    out["BMI"] = df["_BMI5"] / 100.0
    out["GenHlth"] = df["GENHLTH"].where(df["GENHLTH"].between(1, 5))
    out["PhysHlth"] = df["PHYSHLTH"].replace(88, 0).where(df["PHYSHLTH"].isin(list(range(0, 31)) + [88]))
    out["MentHlth"] = df["MENTHLTH"].replace(88, 0).where(df["MENTHLTH"].isin(list(range(0, 31)) + [88]))
    out["DiffWalk"] = clean_yesno(df["DIFFWALK"])
    out["Smoker"] = clean_yesno(df["SMOKE100"])
    out["Stroke"] = clean_yesno(df["CVDSTRK3"])
    heart_attack = clean_yesno(df["CVDINFR4"])
    chd = clean_yesno(df["CVDCRHD4"])
    out["HeartDiseaseorAttack"] = ((heart_attack == 1) | (chd == 1)).astype("Int64")
    out["NoDocbcCost"] = clean_yesno(df["MEDCOST1"])
    out["source_year"] = 2024

    out = out.dropna()
    cols = ["Smoker", "HeartDiseaseorAttack", "Stroke", "BMI", "Age", "DiffWalk",
            "PhysHlth", "GenHlth", "MentHlth", "NoDocbcCost", "Sex", "source_year"]
    out = out[cols].astype({c: int for c in cols if c != "BMI"})
    out = out[(out["BMI"] >= 12) & (out["BMI"] <= 80)]
    out.to_csv("data/neuropathy_dataset.csv", index=False)
    print(f"neuropathy_dataset.csv: {len(out)} rows (raw 2024 BRFSS diabetic-positive respondents)")
    return out


if __name__ == "__main__":
    print("Building category-specific datasets from 2021-2024 BRFSS data...")
    build_cardio_dataset()
    build_general_burden_dataset()
    build_neuropathy_dataset()
    print("Done.")
