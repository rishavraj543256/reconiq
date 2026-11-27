from decimal import Decimal
import numpy as np
from sklearn.ensemble import IsolationForest


class AnomalyDetector:
    def detect(self, records: list[dict]) -> list[dict]:
        if len(records) < 5:
            return []
        amounts = np.array([float(abs(Decimal(str(x["amount"])))) for x in records])
        days = np.array([x["transaction_date"].toordinal() for x in records])
        features = np.column_stack([np.log1p(amounts), days - days.min()])
        model = IsolationForest(n_estimators=100, contamination=min(0.15, 2 / len(records)), random_state=42)
        predictions = model.fit_predict(features)
        scores = -model.decision_function(features)
        median = float(np.median(amounts))
        output = []
        for record, prediction, score, amount in zip(records, predictions, scores, amounts):
            if prediction != -1:
                continue
            severity = "high" if score > 0.1 else "medium"
            reason = f"Amount {amount:.2f} is atypical relative to the tenant median {median:.2f}; this is an anomaly signal, not confirmed fraud."
            output.append({"transaction_id": record["id"], "score": float(score), "severity": severity, "explanation": reason})
        return output
