# ChangeImpactBench · V6 counterfactual UI

The application has two navigation destinations: **Run a Test** and **Results**. The standalone Incident Lab was removed; the dependency map now appears during a live investigation, with all service health states deliberately marked unknown until independent verification. The live workflow marks steps only from recorded provider and tool events. It never displays simulated chain-of-thought or makes up an execution status.

## Run a Test

Choose one of six `RW01V6CF`–`RW06V6CF` incidents, select 1–5 supported provider models, and choose 1–5 trials per model. Explicitly approve a bounded number of real provider calls. Then click **Start Investigation**. The live panel shows the model's recorded inspection, repair planning, simulation, commitment, diagnosis submission, verification, and latest tool observations. An empty workflow step means it has not yet been recorded; it is not proof of failure. The topology diagram is reference context for the reviewer, not a map the model necessarily saw.

**Advanced settings:** cumulative provider-reported input-token budget per trial (4,096–10,000,000; default 1,000,000), max output tokens per model response (512–20,000; default 8,000, subject to selected provider/model support), reasoning effort, temperature, and delay. Input-budget enforcement blocks the **next** request after the reported threshold is reached. Provider counts arrive after each response, so the final request may cross the limit; this is not an exact per-request context-window cap. Missing provider usage prevents any further requests. Report token usage and provider-specific reasoning settings carefully; some providers ignore reasoning controls. When comparing models, report the exact generation settings and token usage.

## Results

Show saved trials, independently verified strict verdict, grade, why a trial passed or failed, and comparisons of matching task versions. **View full evidence** opens the detailed audit and recorded tool trace, review, and raw exports. No artificial model scores are embedded in the UI.

## Running locally

Run `(cd web && npm ci && npm run lint && npm run build)` before release. Development: `(cd web && npm run dev)`, FastAPI at `http://127.0.0.1:8000`. Keep provider keys server-side in the project `.env`; never expose them in Next.js. The backend uses LangChain `create_agent` / LangGraph and deterministic Python replay for all six distinct counterfactual references. See the repository root README for evaluation and reproducibility methodology.
