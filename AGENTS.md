# AGENTS.md — DiaBeates Design, Styling, Architecture & Engineering Guide

This document is the single source of truth for all AI agents, engineers, and designers working on **DiaBeates**. Whenever future prompts or tasks are requested, all work must adhere to the design system, plain-language standards, clinical safety rules, and technical invariants documented here to ensure complete visual, functional, and architectural consistency across the application.

---

## 1. Project Context & Audience

- **What DiaBeates Is**: A clinical decision support web application built with Flask, Jinja2, Tailwind CSS, and SQLite for diabetes complication risk screening.
- **Primary Audience**: Patients, caregivers, and primary care providers in the Philippines who take a 15-question intake to screen for 4 complication risks:
  1. **Heart** (*Cardiovascular / ASCVD*)
  2. **Kidneys** (*Nephropathy / CKD / KDIGO*)
  3. **Nerves and feet** (*Neuropathy & Mobility / MNSI*)
  4. **Eyes** (*Retinopathy / AAO*)
- **Primary Device**: Mobile phones (smartphones on cellular connections), followed by desktop browsers at local health clinics.
- **Tone & Mood**: Calm, credible, warm, friendly, plain-spoken, like a trusted public health campaign poster or a well-crafted medical reference—**never** a flashy Silicon Valley health-tech startup.

---

## 2. Inviolable Backend & Clinical Constraints ("DO NOT TOUCH")

When performing any frontend, UX, design, or UI copy work, **NEVER MODIFY**:
1. **Core Backend Logic**:
   - `app.py` routing logic, prediction endpoints, session management, or encryption handling.
   - `rule_matrix.py` clinical scoring matrices.
   - `clinical_model.py` and model loading.
   - `validation.py` input validation rules and numeric bounds.
   - `database.py` database schema, persistence, and safe migration routines.
   - `recommendations.py` decision logic and recommendation triggers.
   - Trained machine learning weights in `model/*.pkl`.
2. **Clinical Data & Metrics**:
   - Do NOT alter any clinical thresholds, point allocations, cutoffs, or formulas.
   - Do NOT alter model validation metrics (AUROC, Brier scores, calibration slope/intercept).
   - Only change *how* and *where* they are displayed (see Progressive Disclosure below).
3. **Form & Accessibility Signatures**:
   - Preserve all form field names (`Age`, `Sex`, `BMI`, `HighBP`, `HighChol`, `Smoker`, `HeartDiseaseorAttack`, `Stroke`, `DiffWalk`, `PhysHlth`, `GenHlth`, `MentHlth`, `NoDocbcCost`, `DiabetesDuration`, `BlurryVision`, `LabHbA1c`, `LabSystolicBP`, `LabLDL`).
   - Preserve all CSRF token fields (`<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`).
   - Preserve all critical element IDs and accessibility attributes tested by automated test suites.

---

## 3. Forbidden "AI Tells" & Anti-Patterns

Never introduce or restore the following patterns. They make the site look like a generic AI template:
- ❌ **No Glassmorphism & Blur**: Never use `backdrop-blur`, semi-transparent glass cards, floating blurred orbs, or mesh gradient backgrounds.
- ❌ **No Conic / Animated Borders**: Never use `.animated-border-card`, `.scan-light-card`, or rotating conic gradient borders.
- ❌ **No Page Transition Overlays**: Never use full-screen breathing or pulsing logo overlays (`startTransition`, `logoBreath`, `logoGlowPulse`, `pageReveal`). Page loads must feel instantaneous and native.
- ❌ **No Ambient Background Videos**: Never place auto-playing background videos behind page text (e.g. `medical_workers.mp4` behind content).
- ❌ **No Decorative Card Clutter**: Never use 4 identical dark-teal complication cards, 3-column generic icon feature grids, or centered heroes with redundant CTAs.
- ❌ **No Circular SVG Gauges**: Never use circular speedometer/gauge SVGs as the primary complication display.
- ❌ **No Generic Font Stacks / External CDNs**: Never link to Google Fonts or external CDN styles (CSP is locked to `default-src 'self'`).
- ❌ **No Neon Cyans & Gradients**: Never use `#03bdcd`, `#37f6f2`, `.gradient-primary`, or linear gradient backgrounds.
- ❌ **No Tech Buzzwords**: Never use buzzwords like *"Dual-Engine Precision"*, *"Actionable Explainability"*, *"Patient Empowerment"*, *"Clinical Decision Support Pre-Screening Paradigm"*, etc.

---

## 4. Plain-Language & The "12-Year-Old Test"

Every patient-facing screen must pass this test: **A 12-year-old or an elder with no medical training must understand it in 5 seconds.**

### Plain-Language Translation Rules:
| Medical / Technical Jargon | Plain-Language Replacement |
| :--- | :--- |
| **Cardiovascular / ASCVD** | **Heart** |
| **Nephropathy / Renal / CKD** | **Kidneys** |
| **Neuropathy / Mobility / MNSI** | **Nerves and feet (walking)** |
| **Retinopathy / AAO** | **Eyes** |
| **HbA1c** | **3-month sugar test (HbA1c)** |
| **Systolic BP** | **Top blood pressure number** |
| **LDL Cholesterol** | **Bad cholesterol (LDL)** |
| **Hypertension** | **High blood pressure** |
| **Risk drivers / Features** | **What affects this** |
| **Surveillance** | **Check-ups** |

### Writing Guidelines:
- **Reading Level**: Grade 6.
- **Sentence Length**: Under 12 words per sentence.
- **Paragraphs**: Maximum 2 short lines on the primary path. Prefer a badge, label, or illustration over a paragraph.
- **Local Context**: Use familiar Philippine examples when providing health context (e.g., rice portions, walking after meals, merienda, sari-sari store snacks, softdrinks, barangay health center visits).

---

## 5. Progressive Disclosure Architecture

Clinical depth must **never** be removed from DiaBeates, but it must **never** clutter the primary patient flow.

- **Primary Path (For Patients & Caregivers)**:
  - Large SVG illustration of the organ (Heart, Kidneys, Foot, Eye).
  - One-word complication title.
  - Plain triage status badge: **Good**, **Check**, or **See a doctor** (always icon + word).
  - 1–2 plain-language sentences describing what this means and what affects it.
  - Specific questions to ask their doctor.
  - For Retinopathy: Always include the plain disclaimer: *"The eye result is less certain than the others. Please get an eye exam either way."*
- **Technical Disclosure (For Primary Care Providers & Doctors)**:
  - Hidden by default inside an accessible `<details><summary class="cursor-pointer font-bold text-[#0b7a85]">For your doctor: technical details</summary>...</details>` element.
  - Contains: Rule-matrix point breakdown, ML probability (%), calibrated algorithm name, model AUROC, Brier score, guideline citations (ACC/AHA, KDIGO 2024, MNSI, UKPDS, AAO), and lab target tables.

---

## 6. Design System & Tokens (`static/css/clinical.css`)

### Color Palette (CSS Variables in `:root`):
```css
:root {
  /* Warm Public Health Surfaces */
  --cream: #fbf6ec;        /* Page background */
  --sand: #f3e9d6;         /* Alternating section bands */
  --white: #ffffff;        /* Card and input background */
  --border-cream: #e5dcce; /* Hairline borders */

  /* Inks & Text */
  --ink: #1f2a33;          /* High contrast primary text */
  --ink-muted: #4f5b66;    /* Secondary explanatory text */
  --navy: #063154;         /* Headings, accents, primary buttons */

  /* Interactive Accent */
  --teal: #0b7a85;         /* Primary links, focus rings, toggles */
  --teal-hover: #08616a;
  --teal-light: #e6f4f5;

  /* Accents (Use Sparingly) */
  --marigold: #f2a73b;     /* Warm highlights */
  --coral: #e8765a;        /* Warning accents */

  /* Triage Tiers (ALWAYS paired with icon + text label) */
  --status-good-text: #2f7d4a;
  --status-good-bg: #e4f2e7;
  --status-good-border: #bce0c6;

  --status-check-text: #a86a0a;
  --status-check-bg: #fbeed0;
  --status-check-border: #f4d99f;

  --status-doctor-text: #b03a2e;
  --status-doctor-bg: #f9e1dc;
  --status-doctor-border: #f1b8af;
}
```

### Self-Hosted Typography:
All font files are self-hosted in `static/fonts/` (no external CDNs due to strict CSP):
- **Headings**: `Fraunces` (700 bold), line-height 1.15, clamp scale (32px to 56px).
- **Body & Controls**: `Source Sans 3` (400 regular, 500 medium, 600 semibold). Minimum 18px on mobile for maximum legibility.
- **Numbers, Scores, Labs, Timestamps**: `IBM Plex Mono` (400, 600) with tabular figures.

### Accessibility & Interaction:
- **Touch Targets**: Minimum 48px height across all buttons, selects, and inputs (`min-height: 48px`).
- **Focus Rings**: Visible 2px teal outline (`outline: 2px solid var(--teal) !important; outline-offset: 2px !important;`).
- **Borders & Shadows**: 1px solid border (`#e5dcce`), border radius 8px (buttons/inputs), 12px (cards), 16px (dialogs). Subtle elevation (`0 1px 2px rgba(31, 42, 51, 0.06)`).

---

## 7. Page-Specific Specifications

### 1. Home (`templates/home.html`)
- **Hero Section**:
  - Headline: *"Check your health risks in 3 minutes."*
  - Subtitle: *"Free. No name or email needed."*
  - Primary Action: One prominent button *"Start check"* linking to `/assessment`.
  - Imagery: Authentic photo of a Filipino family (`static/img/filipino_family_hero.webp`).
- **How It Works**: 3 numbered, illustrated steps:
  1. *Answer 15 easy questions*
  2. *See your results*
  3. *Know what to ask your doctor*
- **What We Check**: 4 large visual complication cards (Heart, Kidneys, Nerves and feet, Eyes) with 2px line SVG illustrations (`templates/macros/illustrations.html`).
- **Privacy Reassurance**: Clear card confirming no personal identifiers (name, email, phone) are requested or stored.
- **No Video Container**: Do **not** re-add the video container (`health-card p-4 sm:p-6`) on the homepage.

### 2. Assessment Wizard (`templates/assessment.html`)
- **Step 1: About you**
  - Age range dropdown (`#Age`).
  - Sex assigned at birth dropdown (`#Sex`).
  - General health rating dropdown (`#GenHlth`).
  - Diabetes duration dropdown (`#DiabetesDuration`).
  - **BMI Section**:
    - Number input: `<input type="number" step="0.1" min="10" max="80" name="BMI" id="BMI" required>`.
    - Label: `<label for="BMI">Body Mass Index (BMI)</label>`.
    - Prominent trigger button: `<button type="button" id="openBmiCalcBtn" aria-haspopup="dialog" aria-controls="bmiModal">` with text **"Don't know your BMI?"** and calculator SVG icon.
    - Category indicator next to input: `<span id="onPageBmiCategory"></span>` dynamically updating with the clinical category.
- **Step 2: Your health**
  - 8 large visual choice tiles with check indicators:
    1. `HighBP` (High blood pressure)
    2. `HighChol` (High cholesterol)
    3. `Smoker` (Smoking history)
    4. `HeartDiseaseorAttack` (Heart trouble / attack)
    5. `Stroke` (Stroke history)
    6. `DiffWalk` (Difficulty walking / climbing stairs)
    7. `BlurryVision` (Blurry vision / eye issues)
    8. `NoDocbcCost` (Skipped doctor visit due to cost)
  - Slider controls for physical health days (`PhysHlth`) and mental health days (`MentHlth`) with 30-day cap warning and `#capPhysHlthBtn` / `#capMentHlthBtn`.
- **Step 3: Lab results (optional)**
  - Collapsible toggle (`#hasLabsToggle`) that opens `#labsInputsPanel`.
  - Optional inputs for `LabHbA1c` (%), `LabSystolicBP` (mmHg), and `LabLDL` (mg/dL).
  - Submit button `#submitBtn` with loading state: *"Checking your results..."*.

### 3. Interactive BMI Calculator Modal (`templates/assessment.html`)
The modal must exist as `<dialog id="bmiModal" aria-labelledby="bmiModalTitle" aria-modal="true">`:
- **Close Button**: `id="closeBmiModalBtn"` with accessible label.
- **Tabs**: `id="tabMetric"` (cm / kg) and `id="tabImperial"` (ft, in / lbs).
- **Panels**:
  - `id="panelMetric"` with `#bmiMetricHeight` (cm) and `#bmiMetricWeight` (kg).
  - `id="panelImperial"` with `#bmiImpFt` (ft), `#bmiImpIn` (in), and `#bmiImpLbs` (lbs).
- **Live Preview**: `id="bmiPreviewBox"` with `#bmiPreviewNum` and `#bmiPreviewCategory`.
- **Validation Alert**: `<p id="bmiModalError" role="alert" class="hidden ..."></p>`.
- **Actions**: `id="cancelBmiBtn"` and `id="applyBmiBtn"`.
- When applied, it writes the value to `#BMI`, dispatches `input` and `change` events, updates `#onPageBmiCategory`, and closes the dialog.

### 4. Results Page (`templates/result.html`)
- Overall Triage Summary Banner with icon, tier name, and plain guidance.
- 4 Domain Complication Cards (Heart, Kidneys, Nerves and feet, Eyes) with:
  - Status badge (Good, Check, See a doctor).
  - What this means (Grade 6 explanation).
  - What affects this (Positive habits vs. elevated risk drivers).
  - Questions to ask your doctor.
  - Closed `<details>` for technical doctor details (rule-matrix points, ML calibrated probability %, AUROC, Brier, guideline citation).
- Optional Lab-Based Assessment Panel (when labs are entered).
- Primary Actions:
  - Save or print report (`/history/<id>/print`).
  - Start new check (`/assessment`).

### 5. Printable Report (`templates/print_result.html`)
- Clean, high-density, black-and-white / dark-ink printable medical summary designed for primary care doctor consultation.
- Includes patient intake summary, 4 complication domain evaluations, lab analysis (if present), and primary care recommendations.

### 6. Session History (`templates/history.html`)
- Tabular record of assessments completed during the session.
- Columns: Assessment date/time in Philippine Time (PHT), complication risk chips, and link to printable report.

---

## 8. Test Invariants & Quality Assurance Runbook

Before completing any task, **always execute all three verification test suites**:

```bash
# 1. Verify clinical engine, security headers, database WAL, WCAG accessibility, and BMI modal IDs
python test_clinical_system.py

# 2. Verify Flow A (with lab inputs) and Flow B (without lab inputs, graceful degradation)
python test_both_flows.py

# 3. Verify live browser simulation, CSRF protection, and history persistence
python live_browser_test.py
```

### Critical DOM Assertions Required by Tests:
- `'id="BMI"' in templates/assessment.html`
- `'for="BMI"' in templates/assessment.html`
- `'id="bmiModal"' in templates/assessment.html`
- `'role="alert"' in templates/assessment.html`
- `'name="csrf_token"' in all form templates`
- `'Cardiovascular (ACC/AHA)' in templates/result.html` (inside doctor technical details)
- `'Start Risk Assessment' in templates/home.html` (accessible screen-reader label on primary button)

---

## 9. Branching & Git Discipline

- The base branch for deployed stable code is `main`.
- Active frontend styling and UI/UX work is developed on `frontend/revamp`.
- Never commit runtime SQLite databases (`*.db`, `*.sqlite*`), DPAPI keys (`.db.key.dpapi`), or large backup zip archives to Git. Ensure `.gitignore` is respected.
