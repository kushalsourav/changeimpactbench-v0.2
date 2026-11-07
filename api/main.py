"""ChangeImpactBench API — thin application composition (agentic-only)."""
from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tasks import ROOT
from api.routes import health, tasks, comparison, runs, review, experiment, synthesis, archive

load_dotenv(ROOT / '.env', override=False)
app = FastAPI(title='ChangeImpactBench Evidence API', version='0.9.21')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000', 'http://127.0.0.1:3000'],
    allow_credentials=False,
    allow_methods=['GET','POST'],
    allow_headers=['Content-Type'],
)
for module in (health, tasks, comparison, runs, review, experiment, synthesis, archive):
    app.include_router(module.router)

# Compatibility imports for existing local test consumers; use api.routes/services
# in newly authored code. No legacy model runner can be launched by the API.
from api.routes.experiment import LaunchRequest  # noqa: E402,F401
from api.services.storage import file_path  # noqa: E402,F401
