import numpy as np
from sklearn.ensemble import IsolationForest

class AnomalyDetector:
    def __init__(self, contamination=0.1):
        self.model = IsolationForest(contamination=contamination, random_state=42)
        self.trained = False
        self.data_buffer = []

    def fit(self, data):
        """Fit the model with collected feature data.
           Data should be a list of feature vectors (e.g. [temperature, humidity])."""
        X = np.array(data)
        self.model.fit(X)
        self.trained = True

    def predict(self, data_point):
        """Predict if a new data point is normal (1) or an anomaly (-1).
           If there is not enough data, returns 1 (normal) by default."""
        if not self.trained or len(self.data_buffer) < 20:
            return 1
        prediction = self.model.predict(np.array(data_point).reshape(1, -1))
        return prediction[0]

    def update(self, data_point):
        """Add a new data point and retrain the model periodically."""
        self.data_buffer.append(data_point)
        # Retrain if we have gathered enough new data
        if len(self.data_buffer) >= 20:
            self.fit(self.data_buffer)
