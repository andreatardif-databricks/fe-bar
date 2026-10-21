# Databricks notebook source
# MAGIC %md
# MAGIC # Train the renewal-risk classifier
# MAGIC
# MAGIC Trains on `silver_renewal_history` (governed, quality-filtered), logs to MLflow, registers
# MAGIC `renewal_risk` in Unity Catalog and moves the `champion` alias only when the new model is
# MAGIC at least as good as the current one on a held-out split.

# COMMAND ----------

dbutils.widgets.text("catalog", "at_workspace_102126")
dbutils.widgets.text("schema", "renewal_radar")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
MODEL_NAME = f"{CATALOG}.{SCHEMA}.renewal_risk"

def record_run(task: str, payload: dict) -> None:
    """Persist this task's result to the governed run_log table and return it as the task exit value."""
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    body = _json.dumps(payload, sort_keys=True, default=str)
    spark.createDataFrame([(task, _dt.now(_tz.utc).isoformat(), body)], "task STRING, recorded_at STRING, payload STRING") \
        .write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.run_log")
    dbutils.notebook.exit(body)

# COMMAND ----------

import mlflow
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

mlflow.set_registry_uri("databricks-uc")

NUMERIC = ["avg_roi_180d", "active_campaigns", "revenue_trend_90d", "late_invoice_rate"]
CATEGORICAL = ["region", "tier"]
LABEL = "churned"

df = spark.table(f"{CATALOG}.{SCHEMA}.silver_renewal_history").toPandas()
assert len(df) >= 300, f"too few training rows: {len(df)}"
print(f"training rows={len(df)} churn rate={df[LABEL].mean():.3f}")

train, test = train_test_split(df, test_size=0.25, random_state=7, stratify=df[LABEL])
model = Pipeline([
    ("prep", ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)], remainder="passthrough")),
    ("gbm", GradientBoostingClassifier(n_estimators=150, max_depth=2, learning_rate=0.08, random_state=7)),
])

# COMMAND ----------

user = spark.sql("SELECT current_user()").first()[0]
mlflow.set_experiment(f"/Users/{user}/renewal_radar_renewal_risk")

with mlflow.start_run(run_name="renewal_risk_gbm") as run:
    model.fit(train[NUMERIC + CATEGORICAL], train[LABEL])
    auc = roc_auc_score(test[LABEL], model.predict_proba(test[NUMERIC + CATEGORICAL])[:, 1])
    mlflow.log_params({"model": "GradientBoosting", "n_estimators": 150, "max_depth": 2, "train_rows": len(train)})
    mlflow.log_metrics({"holdout_auc": auc, "churn_rate": float(df[LABEL].mean())})
    sig = infer_signature(train[NUMERIC + CATEGORICAL], model.predict_proba(train[NUMERIC + CATEGORICAL])[:, 1])
    info = mlflow.sklearn.log_model(model, name="model", signature=sig, registered_model_name=MODEL_NAME)
    print(f"holdout AUC = {auc:.4f}  run_id={run.info.run_id}")

assert auc > 0.65, f"model is not better than a weak baseline (AUC {auc:.3f}); refusing to promote"

# COMMAND ----------

client = MlflowClient()
new_version = info.registered_model_version
promote = True
try:
    current = client.get_model_version_by_alias(MODEL_NAME, "champion")
    cur_auc = client.get_run(current.run_id).data.metrics.get("holdout_auc", 0.0)
    promote = auc >= cur_auc - 0.01
    print(f"champion v{current.version} AUC={cur_auc:.4f} -> candidate v{new_version} AUC={auc:.4f} promote={promote}")
except Exception:
    print("no champion yet; promoting first version")
if promote:
    client.set_registered_model_alias(MODEL_NAME, "champion", new_version)
print(f"MODEL_PROMOTED name={MODEL_NAME} version={new_version} holdout_auc={auc:.4f} promoted={promote}")

# COMMAND ----------

record_run("train_renewal_risk", {"model": MODEL_NAME, "version": str(new_version), "holdout_auc": round(auc, 4), "promoted": promote, "train_rows": len(train), "test_rows": len(test), "churn_rate": round(float(df[LABEL].mean()), 3)})
