# Databricks notebook source
"""
Provision the Lakebase Database Instance and the logical Postgres database that
the synced tables land in.

Uses the modern `w.database` SDK surface:

  * `create_database_instance_and_wait`: idempotent provisioning with a built-in
    waiter (replaces the older `create_database_instance(...).result(timeout=)`
    pattern).
  * `get_database_instance`: cheap existence + status probe.
  * `create_database_instance_role`: declarative federation of a Databricks
    identity (user or service principal) as a Postgres role on this instance.
    Use this in follow-up grant scripts instead of the manual
    `SELECT databricks_create_role(...)` SQL hack.

TODO: when the new `w.database.postgres` PostgresAPI ships in `databricks-sdk`
(documented at https://databricks-sdk-py.readthedocs.io/en/stable/workspace/postgres/postgres.html),
migrate this script to use that surface. Until then, the calls below are the
current public API for Lakebase legacy Database Instances and still cover every
operation that script does.

Safe to re-run: every step is idempotent (instance, database).
"""
import os
import time
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import DatabaseInstance

# Variables: defaults match the live demo. Override via environment when
# deploying into a different workspace.
INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "influencer-fe-bar-lb")
DB_NAME       = os.environ.get("LAKEBASE_DATABASE_NAME", "influencer_fe_bar")
INSTANCE_CAPACITY = os.environ.get("LAKEBASE_CAPACITY", "CU_1")
INSTANCE_NODES    = int(os.environ.get("LAKEBASE_NODE_COUNT", "1"))

w = WorkspaceClient()


# ----------------------------------------------------------------------
# 1. Database Instance (idempotent)
# ----------------------------------------------------------------------
existing = None
try:
    existing = w.database.get_database_instance(name=INSTANCE_NAME)
except Exception as e:
    # SDK versions format a missing instance as NotFound, Resource not found,
    # or an HTTP 404. All three are safe to treat as an absent resource.
    msg = str(e).lower()
    if not any(marker in msg for marker in ("notfound", "not_found", "not found", "404")):
        raise

if existing is not None:
    print(f"Database instance '{INSTANCE_NAME}' already exists  "
          f"(state={existing.state}, host={existing.read_write_dns})")
else:
    print(f"Creating database instance '{INSTANCE_NAME}' "
          f"(capacity={INSTANCE_CAPACITY}, nodes={INSTANCE_NODES})...")
    spec = DatabaseInstance(
        name=INSTANCE_NAME,
        capacity=INSTANCE_CAPACITY,
        node_count=INSTANCE_NODES,
    )
    # create_database_instance_and_wait: replaces the older two-call pattern
    # `create_database_instance(...).result(timeout=...)`. Built-in waiter
    # polls until state=AVAILABLE.
    existing = w.database.create_database_instance_and_wait(database_instance=spec)
    print(f"  ready  state={existing.state}  host={existing.read_write_dns}")


# ----------------------------------------------------------------------
# 2. Logical Postgres database (idempotent, via psycopg)
#    The SDK does not yet expose a `create_database`/`logical-database` call;
#    do it inline against the admin database. When the new postgres SDK lands
#    this becomes `w.database.postgres.databases.create(...)` (TODO).
# ----------------------------------------------------------------------
import psycopg

host = existing.read_write_dns
user = w.current_user.me().user_name
token = w.database.generate_database_credential(
    request_id=f"setup-lakebase-{int(time.time())}",
    instance_names=[INSTANCE_NAME],
).token

conn_str = (
    f"host={host} dbname=databricks_postgres user={user} "
    f"password={token} sslmode=require"
)
print(f"\nConnecting to {host} as {user} (admin db)...")
with psycopg.connect(conn_str, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        if cur.fetchone():
            print(f"  Logical database '{DB_NAME}' already exists.")
        else:
            cur.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"  Created logical database '{DB_NAME}'.")


# ----------------------------------------------------------------------
# 3. Helper note: federating Databricks identities as Postgres roles
# ----------------------------------------------------------------------
# Use:
#   w.database.create_database_instance_role(
#       instance_name=INSTANCE_NAME,
#       database_instance_role=DatabaseInstanceRole(
#           name="<sp-application-id-or-user-name>",
#           identity_type=DatabaseInstanceRoleIdentityType.SERVICE_PRINCIPAL,  # or USER
#       ),
#   )
# instead of the manual `SELECT databricks_create_role(...)` SQL workaround.
# That step lives in the grant phase (see README.md "Quick start" step 5b), not
# in this script, because the app SP doesn't exist until `pulsar_app` is deployed.
print(
    f"\nReady. "
    f"INSTANCE_NAME={INSTANCE_NAME}  "
    f"DB_NAME={DB_NAME}  "
    f"HOST={host}"
)
