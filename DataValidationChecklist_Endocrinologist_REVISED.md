# DiaBeates
## Clinical Review Checklist: Diabetes Complication Screening Prototype

### Purpose and reviewer instructions

**Project:** DiaBeates, a preliminary diabetes complication screening prototype  
**Requested reviewer:** Licensed endocrinologist, diabetologist, or internal-medicine specialist  
**Review purpose:** Expert review of clinical plausibility, terminology, scoring assumptions, patient-facing language, and safety guardrails

DiaBeates is an academic, web-based screening prototype for adults with established diabetes. It is **not a diagnostic device, treatment tool, emergency triage service, or replacement for clinical assessment**. It has not been cleared or approved by a regulatory authority.

The prototype presents two separate outputs:

1. A points-based rule summary of self-reported factors.
2. A model-estimated probability derived from population health data.

These outputs use different methods and must not be interpreted as equivalent measures. A rule score is not a clinical probability, and a model estimate does not confirm or exclude disease.

Please mark **Acceptable**, **Requires Revision**, or **Not Acceptable** for each section. Please identify the specific correction needed wherever possible. This review is requested as scholarly expert feedback; it is not being presented as formal clinical validation or regulatory approval.

---

## Part 1: Domain names and clinical scope

Please assess whether each domain is named and described accurately for a screening prototype.

| Domain shown to patient | Proposed scope | Current evidence boundary | Acceptable | Requires revision | Not acceptable | Reviewer comments |
|---|---|---|---|---|---|---|
| Cardiovascular risk factors | Self-reported factors associated with cardiovascular risk | Not an ACC/AHA or UKPDS calculator; does not provide a validated 10-year ASCVD estimate | [ ] | [ ] | [ ] | |
| Renal/systemic burden proxy | Self-reported factors associated with renal or overall health burden | Does not stage CKD and does not replace eGFR or urine albumin-to-creatinine ratio testing | [ ] | [ ] | [ ] | |
| Neuropathy/mobility proxy | Self-reported mobility and physical-health indicators | Does not perform an MNSI examination, monofilament test, or nerve-conduction study | [ ] | [ ] | [ ] | |
| Diabetic eye-risk indicators | Self-reported factors associated with need for eye evaluation | Does not examine the retina or diagnose diabetic retinopathy | [ ] | [ ] | [ ] | |

**Requested terminology check:** Please identify any guideline citation that should be removed, narrowed, or replaced. Guideline references should describe the clinical context for the factors, not imply that the prototype implements the referenced calculator or examination.

---

## Part 2: Rule-based scoring

The rule engine assigns points to reported indicators. Please assess whether the factors and relative weights are clinically reasonable as an **educational heuristic**, rather than as validated disease probabilities.

| Domain | Factor | Points | Review question | Acceptable | Requires revision | Not acceptable | Comments |
|---|---|---:|---|---|---|---|---|
| Cardiovascular | Hypertension / reported high blood pressure | +2 | Is this weight reasonable for a qualitative risk-factor summary? | [ ] | [ ] | [ ] | |
| Cardiovascular | Dyslipidemia / reported high cholesterol | +2 | Is the wording sufficiently clear without implying an LDL-based calculation? | [ ] | [ ] | [ ] | |
| Cardiovascular | Current smoking | +2 | Is the factor definition clinically appropriate? | [ ] | [ ] | [ ] | |
| Cardiovascular | Prior heart attack or coronary disease | +3 | Should this be displayed as established cardiovascular disease rather than a generic risk factor? | [ ] | [ ] | [ ] | |
| Cardiovascular | Prior stroke | +3 | Is this factor and its wording appropriate? | [ ] | [ ] | [ ] | |
| Cardiovascular | BMI category and age band | +1 or +2 | Are these appropriate as contextual factors, with no implication of causation? | [ ] | [ ] | [ ] | |
| Renal/systemic proxy | High blood pressure | +2 | Is this acceptable only as a broad risk indicator, not a CKD measure? | [ ] | [ ] | [ ] | |
| Renal/systemic proxy | Self-rated general health | +1 or +3 | Is this too nonspecific to appear under a renal heading? | [ ] | [ ] | [ ] | |
| Renal/systemic proxy | Mental-health burden | +1 | Should this be removed or moved to a social/health-support context? | [ ] | [ ] | [ ] | |
| Renal/systemic proxy | Cost-related lack of care access | +1 | Is this better described as a care-access flag rather than a disease-risk factor? | [ ] | [ ] | [ ] | |
| Neuropathy/mobility proxy | Difficulty walking or climbing stairs | +3 | Is “mobility impairment” more accurate than “MNSI sign”? | [ ] | [ ] | [ ] | |
| Neuropathy/mobility proxy | Poor physical-health days | +1 or +2 | Is this sufficiently specific to neuropathy? | [ ] | [ ] | [ ] | |
| Neuropathy/mobility proxy | BMI, age, smoking | +1 each | Are these acceptable contextual associations without causal claims? | [ ] | [ ] | [ ] | |
| Diabetic eye-risk indicators | Diabetes duration | +1 to +3 | Is duration presented as an eye-screening context, not a diagnosis? | [ ] | [ ] | [ ] | |
| Diabetic eye-risk indicators | Blurry vision | +3 | Should this trigger symptom-specific clinical advice rather than only a risk score? | [ ] | [ ] | [ ] | |
| Diabetic eye-risk indicators | Blood pressure, cholesterol, smoking | +1 or +2 | Are these appropriate contextual factors? | [ ] | [ ] | [ ] | |

### Score presentation requirement

Any rule result must be displayed as a points-based summary, for example **“13 of 16 rule points”** or **“81% of the rule maximum.”** It must not be labeled as an **81% disease risk** or **81% probability** unless an appropriate outcome-specific validation study supports that interpretation.

---

## Part 3: Optional laboratory information

The prototype accepts self-reported HbA1c, systolic blood pressure, and LDL values. These values are supplementary, may be inaccurate or outdated, and are not imported from a laboratory or medical record.

Please review the following presentation principles rather than treating the bands as universal treatment targets:

| Biomarker | Prototype display | Required qualification | Acceptable | Requires revision | Not acceptable | Comments |
|---|---|---|---|---|---|---|
| HbA1c | Lower, intermediate, and higher bands | Targets vary by individual factors, age, comorbidities, hypoglycemia risk, and pregnancy status | [ ] | [ ] | [ ] | |
| Systolic BP | Lower, intermediate, and higher bands | KDIGO targets apply in specific CKD and standardized office-measurement contexts; they are not universal thresholds | [ ] | [ ] | [ ] | |
| LDL cholesterol | Lower, intermediate, and higher bands | Goals depend on cardiovascular history and overall risk; this is not a treatment recommendation | [ ] | [ ] | [ ] | |

**Guideline version check:** Confirm the exact edition, recommendation number, population, and measurement context for every cited guideline. Do not cite a guideline as though it validates the prototype’s scoring bands unless it explicitly does so.

---

## Part 4: Patient-facing language and safety

### 4A. Required language

| Safety rule | Required behavior | Acceptable | Requires revision | Not acceptable | Comments |
|---|---|---|---|---|---|
| No diagnosis | Say “screening estimate,” “reported factors,” or “may warrant discussion”; never say the patient has or does not have a complication | [ ] | [ ] | [ ] | |
| No treatment prescribing | Do not recommend starting, stopping, or changing medication, insulin, or procedures | [ ] | [ ] | [ ] | |
| No false reassurance | Do not say “normal,” “safe,” or “you do not need medical care” based on a low result | [ ] | [ ] | [ ] | |
| Clear uncertainty | Explain that a low estimate does not rule out disease and a high estimate does not confirm disease | [ ] | [ ] | [ ] | |
| Appropriate follow-up | Encourage routine diabetes care and clinician review when results or symptoms warrant it | [ ] | [ ] | [ ] | |
| Emergency safety messaging | For red-flag symptoms, provide clinically reviewed urgent or emergency-care instructions | [ ] | [ ] | [ ] | |
| Disclaimer | Show prominently: “This is an automated preliminary screening estimate, not a medical diagnosis. It does not replace professional evaluation or emergency care.” | [ ] | [ ] | [ ] | |

The prototype must not make diagnoses or treatment decisions. However, it must not suppress emergency guidance. At minimum, the clinical reviewer should assess handling of chest pain, stroke symptoms, severe hypoglycemia, severe hyperglycemia symptoms, sudden vision loss, and infected foot wounds.

### 4B. Claims that must be avoided

The system must not state:

- “You have diabetic complications.”
- “You do not have diabetic complications.”
- “Your risk is low, so you are safe or do not need a doctor.”
- “Your neuropathy or retinopathy is caused by poor blood-sugar control.”
- “You will have a heart attack if you do not change your lifestyle.”
- Any medication, procedure, or treatment instruction presented as individualized medical advice.

Suggested wording: **“This screening estimate identified factors that may warrant discussion with a qualified healthcare professional. It cannot diagnose or exclude a complication.”**

---

## Part 5: Reproducible sample output review

The sample case must include every input used to calculate every displayed rule score and model result. Please attach the exact input record or appendix before review.

### Required sample fields

Age band, sex, BMI, diabetes type and duration, blood pressure history, cholesterol history, smoking status, prior heart attack/coronary disease, prior stroke, difficulty walking, poor physical-health days, poor mental-health days, general-health rating, cost-related care access, blurry vision, and any laboratory values.

### Sample output review

| Output | Value from the attached reproducible run | Reviewer comments |
|---|---|---|
| Cardiovascular rule score | ____ of ____ points | |
| Renal/systemic proxy rule score | ____ of ____ points | |
| Neuropathy/mobility proxy score | ____ of ____ points | |
| Diabetic eye-risk indicator score | ____ of ____ points | |
| Model estimates and model tiers | Attach exact generated report | |
| Patient-facing recommendations | Attach exact generated report | |
| Overall headline | ______________________________ | |

Please assess whether the headline is clear without overstating urgency. Any symptom that could represent an emergency must be handled by the emergency-safety rule above, not by a vague general headline.

---

## Part 6: Known limitations for acknowledgement

Please confirm that the following limitations are accurately stated and sufficiently prominent:

| Limitation | Clinical implication | Acceptable | Requires revision | Not acceptable | Comments |
|---|---|---|---|---|---|
| Cross-sectional, survey-based cohorts | Associations may not transport to individual patients or establish causation | [ ] | [ ] | [ ] | |
| Renal/systemic proxy lacks eGFR and UACR | It cannot diagnose, stage, or exclude CKD | [ ] | [ ] | [ ] | |
| Mobility endpoint is a functional proxy | Early or asymptomatic neuropathy may be missed | [ ] | [ ] | [ ] | |
| Retinopathy model is supplementary | Eye examination remains the appropriate screening pathway | [ ] | [ ] | [ ] | |
| Self-reported laboratory values | Values may be inaccurate, outdated, or measured under different conditions | [ ] | [ ] | [ ] | |
| Model calibration and discrimination vary by domain | Probabilities and tiers have uncertainty and should not be treated as individual diagnosis | [ ] | [ ] | [ ] | |
| No external prospective validation | Performance in this prototype does not establish clinical effectiveness | [ ] | [ ] | [ ] | |
| Intended population is limited | Not validated for children, pregnancy/gestational diabetes, prediabetes, or people without established diabetes | [ ] | [ ] | [ ] | |
| No treatment or emergency-triage function | Clinical care decisions remain with qualified professionals and emergency services | [ ] | [ ] | [ ] | |

Please attach the model card or evaluation appendix containing cohort sizes, outcome definitions, feature lists, missing-data handling, calibration metrics, discrimination metrics with confidence intervals, thresholds, and subgroup results.

---

## Part 7: Overall expert feedback

Please select one:

- [ ] Clinically plausible for academic demonstration, with the terminology and limitations stated above.
- [ ] Clinically plausible after the revisions identified in this review.
- [ ] Requires substantial clinical revision before being shown to patients.
- [ ] Not suitable for the stated screening purpose.

**Most important required changes:**

__________________________________________________________________

__________________________________________________________________

**Additional comments:**

__________________________________________________________________

**Reviewer name:** ______________________________________________

**Credentials / specialty:** ______________________________________

**Institution:** _________________________________________________

**Signature and date:** __________________________________________

**Important:** This checklist records expert feedback on an academic prototype. It does not constitute clinical validation, medical-device clearance, or authorization to diagnose, treat, or triage patients.
