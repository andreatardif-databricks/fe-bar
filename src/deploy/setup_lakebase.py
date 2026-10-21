# Databricks notebook source
"""Verify the Lakebase Autoscaling resources used by the Traackr app."""
from databricks.sdk import WorkspaceClient

PROJECT = "projects/influencer-fe-bar-lb"
BRANCH = f"{PROJECT}/branches/production"
ENDPOINT = f"{BRANCH}/endpoints/primary"
DATABASE = f"{BRANCH}/databases/db-ri09-9dhl132wxg"

workspace = WorkspaceClient()
project = workspace.postgres.get_project(name=PROJECT)
branch = workspace.postgres.get_branch(name=BRANCH)
endpoint = workspace.postgres.get_endpoint(name=ENDPOINT)
database = workspace.postgres.get_database(name=DATABASE)

if branch.status.current_state.value != "READY":
    raise RuntimeError(f"Lakebase branch is not ready: {branch.status.current_state}")
if endpoint.status.current_state.value not in ("ACTIVE", "IDLE"):
    raise RuntimeError(f"Lakebase endpoint is unavailable: {endpoint.status.current_state}")

print(f"project={project.name} display_name={project.status.display_name}")
print(f"branch={branch.name} state={branch.status.current_state.value}")
print(
    f"endpoint={endpoint.name} state={endpoint.status.current_state.value} "
    f"autoscaling={endpoint.status.autoscaling_limit_min_cu}-{endpoint.status.autoscaling_limit_max_cu} CU"
)
print(f"database={database.name} postgres_database={database.status.postgres_database}")
