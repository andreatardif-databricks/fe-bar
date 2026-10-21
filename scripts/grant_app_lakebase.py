"""Grant the Databricks App identity access to Lakebase Autoscaling tables."""
import argparse
import psycopg
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

parser = argparse.ArgumentParser()
parser.add_argument("--profile", required=True)
parser.add_argument("--app", default="influencer-fe-bar")
parser.add_argument("--endpoint", default="projects/influencer-fe-bar-lb/branches/production/endpoints/primary")
parser.add_argument("--database", default="influencer_fe_bar")
parser.add_argument("--schema", default="influencer_engagement_fe_bar")
args = parser.parse_args()

workspace = WorkspaceClient(config=Config(profile=args.profile))
app = workspace.apps.get(args.app)
principal = app.service_principal_client_id
endpoint = workspace.postgres.get_endpoint(name=args.endpoint)
credential = workspace.postgres.generate_database_credential(endpoint=args.endpoint)
admin_user = workspace.current_user.me().user_name

connection = psycopg.connect(
    host=endpoint.status.hosts.host,
    dbname=args.database,
    user=admin_user,
    password=credential.token,
    sslmode="require",
    autocommit=True,
)
with connection, connection.cursor() as cursor:
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (principal,))
    if cursor.fetchone() is None:
        raise RuntimeError("App service-principal role is missing; attach the autoscaling postgres app resource first")
    print(f"Lakebase Autoscaling role {principal} exists")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS public.api_keys (
          api_key text PRIMARY KEY,
          brand_id text NOT NULL,
          brand_scope text NOT NULL DEFAULT 'account_id'
            CHECK (brand_scope IN ('all','brand_name','account_id')),
          label text NOT NULL,
          is_active boolean NOT NULL DEFAULT true,
          rate_limit_per_min int NOT NULL DEFAULT 60,
          created_at timestamptz NOT NULL DEFAULT now(),
          expires_at timestamptz,
          last_used_at timestamptz,
          use_count bigint NOT NULL DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS public.propagation_changes (
          change_id text PRIMARY KEY,
          entity text NOT NULL CHECK (entity IN ('creator','campaign')),
          entity_id text NOT NULL,
          field text NOT NULL,
          old_value text,
          new_value text,
          brand_id text,
          sequence_no bigint NOT NULL,
          run_id text,
          sync_run_id text,
          sync_retriggered boolean NOT NULL DEFAULT false,
          t_raw timestamptz NOT NULL,
          t_bronze timestamptz,
          t_platinum timestamptz,
          t_lakebase timestamptz,
          t_api timestamptz,
          error text,
          created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    cursor.execute("""
        INSERT INTO public.api_keys (api_key, brand_id, brand_scope, label)
        VALUES ('pk_demo_all', '*', 'all', 'Synthetic FE Bar demo')
        ON CONFLICT (api_key) DO NOTHING
    """)

    cursor.execute(f'GRANT USAGE ON SCHEMA public, "{args.schema}" TO "{principal}"')
    cursor.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{args.schema}" TO "{principal}"')
    cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.api_keys TO "{principal}"')
    cursor.execute(f'GRANT SELECT, INSERT, UPDATE ON TABLE public.propagation_changes TO "{principal}"')

print(f"Granted least-privilege Lakebase access to app {args.app} ({principal})")
