# ChangeImpactBench v0.9.12 — prospective outcome contract

## Verified V3 observation
The RW01V3 Nemotron episode completed with the correct hypothesis H03, A03, nine recovered services, no new outages, and an invalid early `simulate_repair` call. Its **V3** contract therefore remains **strict fail / 95%**. The requirement to call `prepare_repair` before simulation was explicitly present in the V3 public prompt and tool descriptions; it was a real procedural deviation, not an unspecified requirement.

## V4 contract (new data only)
- New task IDs `RW01V4`, `RW02V4`, `RW03V4`. **Same** synthetic cases, hypothesis list, expected repair IDs and costs as V3. They are not newly difficult scenarios.
- Independent replay checks correct exact initial unavailable-service inventory, hypothesis ID, chosen lowest-cost complete safe commit, actual safe complete recovery and citation provenance. An invalid/rejected request is separately recorded and costs five protocol points, but is not itself a strict outcome failure. Prohibited state changes and unsafe commits still fail.
- Prompt explicitly discloses this distinction. V4 `inspect_metrics` no longer includes `is_direct_local_fault`; V4 fault logs no longer say to inspect the relevant configuration values. V3 tool observations are unchanged.
- Episode Evidence now displays each rejected tool's **actual recorded reason**, replacing the misleading generic simulation-budget example.
- Original V3 hash-bound code is copied into `legacy/v0.9.11/` and its SHA-256 manifest verifies its integrity. V3 regrade retains V3 contract and archived hashes. Existing results files stay unchanged.
- Offline V4 reference trajectories are scripted test tools, **not live model runs**; their success is not evidence of model capability. No changes in the real provider run count, no fabricated pass rates.

## Known limitations / do not misrepresent
- RW01 still lacks a realistic unsafe full-availability data-integrity repair: the current A03 restores everything safely, so this eval does NOT yet test that hard tradeoff. Do not add such an action without a new fixture, independent expert validation and task version.
- Citation scoring verifies existence and counts observation kinds; it does NOT automatically prove semantic support of cited evidence or of the free-form explanation. Human review is needed.
- The tool returns precise declarative local rules when inspected; V4 removes direct-fault badges but is still relatively easy. Run stronger models before claiming a frontier failure.
- A complete frontend production build and real OpenRouter execution must be performed in the user's installed WSL environment. This release includes no new provider evidence.
- Historical V3 and prospective V4 pass rates are **incomparable as a pooled metric**. Compare scores separately and clearly identify grading version.

## Local installation and verification
```bash
cd ~/hackathons/changeimpactbench-v0.2
unzip -o /mnt/d/micro1/ChangeImpactBench_v0.9.12_OUTCOME_PATCH.zip
source .venv/bin/activate
pip install -r requirements-agent.txt
python tools/smoke_langgraph.py
bash scripts/check_release.sh
cd web
npm ci
npm run lint
npm run build
```
Restart FastAPI and Next.js; `/api/health` should show `0.9.12` and the Control Room defaults to RW01V4. Avoid the destructive cleanup script. Preserve old experiment records for audit.
