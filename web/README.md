# ChangeImpactBench v0.9.8 · Modular LangGraph-native research UI

Exactly four tabs: **Research Overview**, **Incident Lab**, **Run a test**, **Episode evidence** (Summary, Tool trace, Integrity checks). The backend launches only one native `langchain.agents.create_agent`/LangGraph investigation per approved episode. The five task IDs are AG08V6, AG09V3, AG10V3, AG11V3 and AG12V3. All scenarios and telemetry are locally authored synthetic fixtures, not production incidents.

No model scores are embedded in the UI. With a freshly cleaned `results/` folder, the Overview explicitly displays an empty state. New outcomes come only from provider episodes independently replayed by FastAPI. Hidden chain-of-thought is inaccessible; the observable native tool trajectory is retained.

Run `(cd web && npm ci && npm run lint && npm run build)` on WSL before release. Development: `(cd web && npm run dev)`; FastAPI at http://127.0.0.1:8000. Never put backend API keys in `web/`.

Styling is static, flat, and graph-first: no animations, gradients or unnecessary decorative cards. The actual agent commitment remains distinct from hypothetical repair previews.

## Source layout

- `app/page.tsx` is the thin Next.js entry point.
- `pages/` contains four independent screens.
- `components/ResearchShell.tsx` owns navigation; `components/ui/` holds shared rendering primitives.
- `hooks/useWorkbench.tsx` owns server/selection state shared across screens; `hooks/useExecutionStream.ts` listens for live SSE progress.
- `store/WorkbenchContext.tsx` carries typed state without duplicate fetches.
- `lib/` contains API types and evidence-only explanations.

Historical run files from older engines are excluded by `/api/runs`; use `scripts/clean_native_only.py --apply --drop-runs` to delete them permanently after stopping the servers.

## First-time researcher flow

The first screen explains the research question and, once a real provider episode exists, shows its verified recovery/diagnosis outcome before methodology. The run and incident selectors use readable names but retain exact task/version/provider identifiers. Comparison statistics require at least two completed episodes. The launcher presents only incident/model/approval/start, with advanced settings collapsed. The evidence view summarizes every recorded tool call and exposes raw observations, deterministic replay, and optional human review. Model hidden chain of thought is not available.

## Diagnosis-contract amendment (v0.9.10)

Current cases: `RW01V2`, `RW02V2`, `RW03V2`. A terminal diagnosis now contains a required enumerated `root_cause_id` and a separate `root_cause_explanation`. Episode Evidence displays the scorer's criterion points and strict-failure reasons, distinguishing classification from rejected tool attempts. Old v1 episodes are read-only historical evidence at `/api/archive/runs`, not active comparisons. See `../docs/DIAGNOSIS_CONTRACT_v0.9.10.md`.

## Agent-written handoff and skills (v0.9.11)

Active experiments: `RW01V3`, `RW02V3`, `RW03V3`. The Episode Evidence Summary now displays the recorded model-authored `prepare_repair` brief and a SHA-256 check of the dynamic repair system prompt. The Tool trace shows the handoff as an observed event, and the redacted exception traceback can be inspected for orchestration errors. Historical v1/v2 records are read-only.
