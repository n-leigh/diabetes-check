"""
clinical_model.py
Defines the ClinicalRiskWrapper estimator for clinical complication risk models.
"""

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin


class ClinicalRiskWrapper(BaseEstimator, ClassifierMixin):
    """
    Wraps an underlying probabilistic binary classifier to accept the full 
    FEATURE_COLUMNS DataFrame from the web app, select its specific clinical predictors, 
    and output both calibrated probabilities and clinical risk tiers (Low, Moderate, High).
    """
    def __init__(self, base_estimator, feature_subset, low_threshold=0.20, high_threshold=0.45):
        self.base_estimator = base_estimator
        self.feature_subset = feature_subset
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.classes_ = np.array(["Low", "Moderate", "High"])

    def fit(self, X, y):
        X_sub = X[self.feature_subset]
        self.base_estimator.fit(X_sub, y)
        return self

    def predict_proba(self, X):
        X_sub = X[self.feature_subset]
        return self.base_estimator.predict_proba(X_sub)

    def predict(self, X):
        proba = self.predict_proba(X)[:, 1]
        preds = []
        for p in proba:
            if p <= self.low_threshold:
                preds.append("Low")
            elif p <= self.high_threshold:
                preds.append("Moderate")
            else:
                preds.append("High")
        return np.array(preds)
