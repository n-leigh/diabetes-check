# DiaBeates System Architecture

## Overview
DiaBeates is a Flask-based diabetes complication risk prediction system that combines rule-based scoring with machine learning models. The architecture follows a layered approach with clear separation of concerns.

## Architecture Diagram

```mermaid
graph TB
    subgraph Frontend["🖥️ Frontend Layer"]
        Home["home.html<br/>(Landing Page)"]
        Assessment["assessment.html<br/>(Input Form)"]
        Result["result.html<br/>(Risk Display)"]
        History["history.html<br/>(Session History)"]
        About["about.html<br/>(Documentation)"]
    end

    subgraph "🌐 Web Server"
        Flask["Flask Application<br/>(app.py)"]
    end

    subgraph "🧠 Business Logic Layer"
        Rules["Rule Matrix<br/>(rule_matrix.py)"]
        Recommendations["Recommendations<br/>(recommendations.py)"]
        Validation["Input Validation<br/>(validation.py)"]
        FieldLabels["Field Labels<br/>(field_labels.py)"]
    end

    subgraph "🤖 ML Layer"
        TrainModel["Model Training<br/>(train_model.py)"]
        ModelCache["Trained Models<br/>(model/ directory)"]
        Summary["Training Summary<br/>(training_summary.json)"]
    end

    subgraph "💾 Data Layer"
        Database["SQLite Database<br/>(database.py)"]
        DBAssessments["📊 assessments table"]
        DBResults["📊 risk_results table"]
        DBLabs["📊 lab_assessments table"]
        DBFeedback["📊 feedback table"]
    end

    subgraph "📁 Data Sources"
        TrainingData["Training Dataset<br/>(data/diabetes_dataset.csv)"]
        DataGen["Sample Data Generator<br/>(data/generate_sample_data.py)"]
    end

    subgraph "📦 Static Assets"
        Static["CSS, JS, Images<br/>(static/ directory)"]
    end

    %% Frontend to Flask
    Home --> Flask
    Assessment --> Flask
    Result --> Flask
    History --> Flask
    About --> Flask

    %% Flask to Business Logic
    Flask --> Validation
    Flask --> Rules
    Flask --> Recommendations
    Flask --> FieldLabels

    %% Flask to ML Layer
    Flask --> ModelCache

    %% Flask to Database
    Flask --> Database

    %% Database Schema
    Database --> DBAssessments
    Database --> DBResults
    Database --> DBLabs
    Database --> DBFeedback

    %% ML Training
    TrainingData --> TrainModel
    TrainModel --> ModelCache
    TrainModel --> Summary

    %% Rules use data schema
    Rules --> TrainModel

    %% Frontend Assets
    Static --> Home
    Static --> Assessment
    Static --> Result
    Static --> History

    %% Data Generation
    DataGen --> TrainingData

    style Frontend fill:#e1f5fe
    style Flask fill:#fff3e0
    style "🧠 Business Logic Layer" fill:#f3e5f5
    style "🤖 ML Layer" fill:#e8f5e9
    style "💾 Data Layer" fill:#fce4ec
    style "📁 Data Sources" fill:#ede7f6
```

## Component Description

### 1. **Frontend Layer** (Templates)
- **home.html** - Landing page with feature overview and CTA buttons
- **assessment.html** - Form for patient input (13 health indicators)
- **result.html** - Risk scores display (rule-based + ML model)
- **history.html** - Patient's session-specific assessment history
- **about.html** - Documentation and methodology
- **base.html** - Base template with navigation

### 2. **Web Server** (Flask)
- **app.py** - Main Flask application
  - Routes: `/`, `/assessment`, `/result`, `/history`, `/about`
  - Session management (anonymous session IDs)
  - Loads trained models at startup
  - Coordinates between frontend, business logic, and data layers

### 3. **Business Logic Layer**
- **rule_matrix.py**
  - Three scoring functions: `score_cardiovascular()`, `score_neuropathy_mobility()`, `score_general_burden()`
  - Converts point scores to risk tiers (Low/Moderate/High)
  - Used for both training data generation and live explanations
  
- **recommendations.py**
  - Converts risk tiers into plain-language guidance
  - Generates personalized wellness recommendations
  - Provides overall risk headline
  
- **validation.py**
  - Input validation for form submissions
  - Ensures data integrity before processing
  
- **field_labels.py**
  - Human-readable descriptions of patient indicators
  - Maps fields to display labels

### 4. **ML Layer**
- **train_model.py**
  - Trains three independent classifiers (one per complication category)
  - Splits data: train/test/val sets
  - Models saved as joblib pickles
  
- **model/** directory
  - Trained model files (per category)
  - training_summary.json - Best model names and metrics

### 5. **Data Layer** (SQLite)
- **database.py** - Database abstraction layer
- **assessments** - Raw patient inputs + session_id + timestamp
- **risk_results** - Scored results (rule score, label, ML prediction, confidence)
- **lab_assessments** - Optional lab values (if provided)
- **feedback** - User feedback signals for model improvement

### 6. **Data Sources**
- **diabetes_dataset.csv** - Training data (CDC BRFSS survey)
- **generate_sample_data.py** - Utility for creating test data

### 7. **Static Assets**
- CSS stylesheets (Tailwind-based)
- JavaScript for interactivity
- SVG icons and images

## Data Flow

### Assessment Submission Flow
```
User Input (assessment.html)
    ↓
Flask Route Handler (app.py)
    ↓
Input Validation (validation.py)
    ↓
Rule Matrix Scoring (rule_matrix.py)
    ↓
ML Model Prediction (trained models)
    ↓
Recommendations Generation (recommendations.py)
    ↓
Database Persistence (database.py → SQLite)
    ↓
Result Rendering (result.html)
```

### Model Training Flow
```
Training Data (diabetes_dataset.csv)
    ↓
train_model.py Script
    ↓
Feature Engineering & Normalization
    ↓
Train/Test/Val Split
    ↓
Three Classifiers (CV, Neuropathy, General Burden)
    ↓
Model Serialization (joblib)
    ↓
model/ directory + training_summary.json
```

## Key Design Decisions

1. **Dual Scoring** - Both rule-based (transparent) and ML-based (predictive) scores for each category
2. **Session Privacy** - Anonymous session IDs keep each user's history private
3. **Normalized Schema** - Four-table structure vs. flat JSON for better data organization
4. **Confidence Scores** - Model predictions include probability scores, not just labels
5. **Rule-Based Ground Truth** - Rule matrix used for training data generation for consistency

## Database Schema

| Table | Purpose |
|-------|---------|
| `assessments` | Raw inputs, session tracking, rule version |
| `risk_results` | Score outputs (rule + model) for each category |
| `lab_assessments` | Optional lab value tracking |
| `feedback` | User feedback for continuous improvement |

## Technology Stack

- **Backend**: Python 3, Flask
- **Frontend**: HTML, Tailwind CSS, JavaScript
- **Database**: SQLite
- **ML**: scikit-learn (trained classifiers), joblib (serialization)
- **Data**: pandas

