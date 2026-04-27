import numpy as np
from sklearn.ensemble import IsolationForest


class AnomalyDetector:
    """
    Isolation Forest-based anomaly detector.

    The anomaly score s(X_t) is computed internally by IsolationForest as:
        s(X_t) = 2^(-E(h(X_t)) / c(n))
    where E(h(X_t)) is the mean path length and c(n) is the normalisation
    constant for n samples (average path length of an unsuccessful BST search).

    The classification decision (Eq. 7) uses a threshold delta:
        c* = LZMA  if s(X_t) > delta  (High Priority / Anomaly)
             arg min J(c)  otherwise   (Normal Priority)

    IsolationForest internally maps delta via the contamination parameter:
    contamination=0.1 corresponds to the top 10% of anomaly scores being
    classified as anomalous. The operational delta value is stored explicitly
    as self.delta for transparency and paper consistency.
    """

    def __init__(self, contamination=0.1, delta=0.5, random_state=42):
        """
        Parameters
        ----------
        contamination : float
            Expected proportion of anomalies in the data (0 < contamination < 0.5).
            Used to set the internal score threshold of IsolationForest.
            Default 0.1 (10% anomaly rate), consistent with Section 6.1.
        delta : float
            Explicit anomaly score threshold as referenced in Eq. (7).
            IsolationForest uses contamination to derive this threshold
            internally; delta is stored here for paper consistency and
            analytical extrapolation studies.
            Default 0.5 (scores above 0.5 on the [0,1] scale are anomalous).
        random_state : int
            Seed for reproducibility (random_state=42, Section 6.1).
        """
        self.contamination = contamination
        self.delta = delta              # explicit delta threshold (Eq. 7)
        self.random_state = random_state
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state
        )
        self.trained = False
        self.data_buffer = []

    def fit(self, data):
        """
        Fit the Isolation Forest model on collected feature vectors.
        Data should be a list of feature vectors [temperature, humidity].
        """
        X = np.array(data)
        self.model.fit(X)
        self.trained = True

    def predict(self, data_point):
        """
        Predict if a new data point is normal (1) or anomalous (-1).

        Returns 1 (normal) by default if the model has not been trained
        or fewer than 20 samples have been collected.

        IsolationForest returns:
            1  -> inlier  (normal, s(X_t) <= delta)
           -1  -> outlier (anomaly, s(X_t) > delta)
        """
        if not self.trained or len(self.data_buffer) < 20:
            return 1
        prediction = self.model.predict(np.array(data_point).reshape(1, -1))
        return prediction[0]

    def score(self, data_point):
        """
        Return the raw anomaly score s(X_t) in [0, 1].
        Higher scores indicate greater anomaly likelihood.
        Used for ablation studies and delta threshold analysis.
        """
        if not self.trained:
            return 0.0
        # IsolationForest.decision_function returns negative scores for
        # anomalies; we convert to a [0,1] scale consistent with Eq.
        raw = self.model.decision_function(
            np.array(data_point).reshape(1, -1)
        )[0]
        # Normalise: map from [-0.5, 0.5] range to [0, 1]
        return float(np.clip(0.5 - raw, 0, 1))

    def update(self, data_point):
        """
        Add a new data point and retrain the model periodically.
        Retraining is triggered every 20 samples to adapt to data drift.
        """
        self.data_buffer.append(data_point)
        if len(self.data_buffer) >= 20:
            self.fit(self.data_buffer)
