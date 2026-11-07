# v0.9.9 — Public-postmortem reconstructions and LLM research analysis

This release intentionally retires the active AG08V6–AG12V3 *fictional task family*. It introduces **RW01–RW03** derived from three named published incidents. Real-world causes and event descriptions are backed by external operator publications; machine-readable topology, metrics, numeric constraints, repair choices, and costs are explicitly modeled. These are **not actual production logs**.

Control Room now selects one named public incident, **1–5 distinct free models**, and **1–5 repetitions per model**, in a single queued experiment. Each episode is a native LangChain `create_agent` / LangGraph graph. It may consume up to 48 provider calls. An explicit approval covers the entire model/trial product. The separate LLM analysis can write a headline, interpretations and observations and choose a chart; chart values are derived from independent Python replay, not invented by the LLM. The secondary provider request requires separate approval. The completed synthesized report is stored in a separate SHA-256-bound JSON sidecar, never rewriting official grades.

The v0.9.9 full ZIP includes a dry-run-first destructive cleanup script. **Stop FastAPI and Next.js before cleanup.** It deletes any old runs and T01–T12 fictional seed files on `--apply --drop-runs`, preserving `.env`, `.venv`, node dependencies, and RW01–RW03 source/references. It will not silently merge old benchmark results with this version.

Offline tests use mock graph objects and are NOT empirical model runs. WSL must still run `pip install -r requirements-agent.txt`, `python tools/smoke_langgraph.py`, and `bash scripts/check_release.sh --final`. The summarizer may fail on free models without structured-output support; this is a provider capability limitation, not a verified research outcome. No live provider trials were generated during this release's preparation.

See `docs/PUBLIC_INCIDENT_DATASET_v0.9.9.md` for exact source links, supported historical facts and the reconstruction boundary.
