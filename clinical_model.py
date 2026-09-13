"""
clinical_model.py
Defines the ClinicalRiskWrapper estimator for clinical complication risk models.

Updated to support:
- Dual screening/referral thresholds (replacing low_threshold/high_threshold)
- Model status metadata (validated vs experimental)
- Calibration quality indicator
- Uncertainty level based on bootstrap CI width
"""

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin


class ClinicalRiskWrapper(BaseEstimator, ClassifierMixin):
    """
    Wraps an underlying probabilistic binary classifier to accept the full
    FEATURE_COLUMNS DataFrame from the web app, select its specific clinical predictors,
    and output both calibrated probabilities and clinical risk tiers.

    Tiers are based on dual thresholds:
    - Below screening_threshold  → "Lower Estimated Risk"
    - Between screening and referral → "Moderate Estimated Risk"
    - Above referral_threshold  → "Higher Estimated Risk"
    """

    def __init__(self, base_estimator, feature_subset,
                 screening_threshold=0.20, referral_threshold=0.45,
                 model_status="validated", calibration_quality="fair",
                 uncertainty_level="moderate"):
        self.base_estimator = base_estimator
        self.feature_subset = feature_subset
        self.screening_threshold = screening_threshold
        self.referral_threshold = referral_threshold
        self.model_status = model_status
        self.calibration_quality = calibration_quality
        self.uncertainty_level = uncertainty_level

    @property
    def classes_(self):
        if hasattr(self.base_estimator, "classes_"):
            return self.base_estimator.classes_
        return np.array([0, 1])

    def fit(self, X, y):
        X_sub = X[self.feature_subset]
        self.base_estimator.fit(X_sub, y)
        return self

    def predict_proba(self, X):
        X_sub = X[self.feature_subset]
        probabilities = self.base_estimator.predict_proba(X_sub)
        if probabilities.ndim != 2 or probabilities.shape[1] != 2:
            raise ValueError("Clinical risk models must produce binary probabilities")
        if not np.array_equal(np.asarray(self.classes_), np.array([0, 1])):
            raise ValueError("Clinical risk models must define classes_ as [0, 1]")
        return probabilities

    def predict_with_probability(self, X):
        """Return model category labels and positive-class probabilities together."""
        probabilities = self.predict_proba(X)[:, 1]
        labels = []
        for probability in probabilities:
            if probability <= self.screening_threshold:
                labels.append("Lower Estimated Risk")
            elif probability <= self.referral_threshold:
                labels.append("Moderate Estimated Risk")
            else:
                labels.append("Higher Estimated Risk")
        return np.array(labels), probabilities

    def predict(self, X):
        """Predict risk tier labels based on dual thresholds."""
        labels, _ = self.predict_with_probability(X)
        return labels

    # Backward-compatible properties for old low_threshold / high_threshold access
    @property
    def low_threshold(self):
        return self.screening_threshold

    @property
    def high_threshold(self):
        return self.referral_threshold
