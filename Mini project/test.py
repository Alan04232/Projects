import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

# Example training data
data = {
    "soil": [40, 60, 80, 90, 75, 50],
    "vibration": [0.02, 0.03, 0.07, 0.08, 0.06, 0.02],
    "label": [0, 0, 1, 1, 1, 0]
}

df = pd.DataFrame(data)

X = df[["soil", "vibration"]]
y = df["label"]

model = RandomForestClassifier(n_estimators=100)
model.fit(X, y)

joblib.dump(model, "D:\workspace\Mini project\model.pkl")
print("ML model trained")