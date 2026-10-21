"""Give the app's service principal read access to the synced Lakebase schema.

Run once after the first app deploy (the principal's Postgres role exists once the app is bound):
    python scripts/grant_app_access.py --profile radar-new
"""
import argparse

import psycopg
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

ap = argparse.ArgumentParser()
ap.add_argument("--profile", required=True)
ap.add_argument("--app", default="traackr-renewal-radar")
ap.add_argument("--endpoint", default="projects/renewal-radar-lb/branches/production/endpoints/primary")
ap.add_argument("--database", default="databricks_postgres")
ap.add_argument("--schema", default="renewal_radar")
a = ap.parse_args()

w = WorkspaceClient(config=Config(profile=a.profile))
role = w.apps.get(a.app).service_principal_client_id
host = w.postgres.get_endpoint(name=a.endpoint).status.hosts.host
token = w.postgres.generate_database_credential(endpoint=a.endpoint).token
with psycopg.connect(host=host, dbname=a.database, user=w.current_user.me().user_name, password=token,
                     sslmode="require", autocommit=True) as conn, conn.cursor() as cur:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    assert cur.fetchone(), f"role {role} missing; bind the app's postgres resource first"
    cur.execute(f'GRANT USAGE ON SCHEMA "{a.schema}" TO "{role}"')
    cur.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{a.schema}" TO "{role}"')
    cur.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{a.schema}" GRANT SELECT ON TABLES TO "{role}"')
    print(f"granted read on {a.schema} to {role}")
