import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import api, assistants, store

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.bootstrap()
    yield


app = FastAPI(title="Traackr Renewal Radar API", version="1.0", lifespan=lifespan,
              description="Creator-campaign ROI, modelled renewal risk and persisted AI actions, served from Lakebase.")
app.include_router(api.router)
app.include_router(assistants.router)


@app.middleware("http")
async def access_log(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/v1/") and request.url.path not in ("/v1/health", "/v1/genie/ask", "/v1/campaigns/explain"):
        store.log_request(request.url.path, request.method, response.status_code, (time.perf_counter() - t0) * 1000,
                          None, {"query": str(request.url.query)})
    return response


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
