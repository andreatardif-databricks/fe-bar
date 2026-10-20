"""Traackr — Influencer Revenue API: customer-facing brand-client API + developer playground UI."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from starlette.types import Scope
from .routes import brands as brands_routes
from .routes import entities as entities_routes
from .routes import freshness as freshness_routes
from .routes import admin as admin_routes
from .routes import propagation as propagation_routes
from .routes import bundle as bundle_routes
from .routes import insights as insights_routes
from .routes import genie as genie_routes
from . import auth


class NoCacheStaticFiles(StaticFiles):
    """StaticFiles subclass that disables caching so deploys are picked up immediately."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        n = auth.reload_brand_keys()
        print(f"[startup] {n} active API keys in Lakebase")
    except Exception as e:
        print(f"[startup] could not query api_keys table: {e}")
    yield


app = FastAPI(
    title="Traackr — Influencer Revenue API",
    description="Read-only API for brand clients. Backed by Lakebase mirrors of the Platinum medallion.",
    version="1.0",
    lifespan=lifespan,
)

app.include_router(brands_routes.router)
app.include_router(entities_routes.router)
app.include_router(freshness_routes.router)
app.include_router(admin_routes.router)
app.include_router(propagation_routes.router)
app.include_router(bundle_routes.router)
app.include_router(insights_routes.router)
app.include_router(genie_routes.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Static UI — developer docs + playground
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", NoCacheStaticFiles(directory=_static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def root():
        return FileResponse(
            os.path.join(_static_dir, "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
