"""Create a (legacy) Database Instance for Lakebase, plus the logical database, for synced tables.
The autoscale 'project' API doesn't yet support synced tables, so we use a Database Instance."""
import time
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import DatabaseInstance, DatabaseCatalog

INSTANCE_NAME = "pulsar-influence-lb"
DB_NAME = "dbgen_pulsar_influence"
CATALOG_NAME = "ai_demo_gen"  # we don't need a separate UC catalog; reuse

w = WorkspaceClient()

# Create instance if missing
existing = None
for di in w.database.list_database_instances():
    if di.name == INSTANCE_NAME:
        existing = di
        break

if existing:
    print(f"Database instance '{INSTANCE_NAME}' already exists, state={existing.state}")
else:
    print(f"Creating database instance '{INSTANCE_NAME}'...")
    inst = DatabaseInstance(
        name=INSTANCE_NAME,
        capacity="CU_1",
        node_count=1,
    )
    waiter = w.database.create_database_instance(database_instance=inst)
    result = waiter.result(timeout=__import__('datetime').timedelta(minutes=15))
    print(f"  state={result.state}, host={result.read_write_dns}")
    existing = result

# Create the logical database under this instance via psycopg
import psycopg
host = existing.read_write_dns
user = w.current_user.me().user_name
token = w.database.generate_database_credential(
    request_id="setup-" + str(int(time.time())),
    instance_names=[INSTANCE_NAME],
).token

conn_str = f"host={host} dbname=databricks_postgres user={user} password={token} sslmode=require"
print(f"\nConnecting to {host} as {user}...")
with psycopg.connect(conn_str, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        if cur.fetchone():
            print(f"Database '{DB_NAME}' already exists.")
        else:
            cur.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"Created database '{DB_NAME}'.")

print(f"\nReady. INSTANCE_NAME={INSTANCE_NAME} DB_NAME={DB_NAME} HOST={host}")
