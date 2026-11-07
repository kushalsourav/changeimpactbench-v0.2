# v0.9.17 Control Room Google model selection fix

- Google selection now acts as a single-choice provider group, replacing any prior model selections.
- Selecting an OpenRouter model after Google switches provider automatically. OpenRouter allows up to five models.
- Refresh Models also re-reads `/api/health`, so key configuration changes are reflected after backend restart.
- Launch button provides explicit reason when disabled (backend key not configured, missing approval, or invalid configuration).

## Apply

From WSL project root:

```bash
unzip -o /mnt/d/micro1/ChangeImpactBench_v0.9.17_UI_SELECTOR_FIX_OVERLAY.zip
cd web
node --test tests/*.test.cjs
npm run lint
npm run build
```

Restart both backend and frontend after installing. Check `curl -s http://127.0.0.1:8000/api/health` for `google_key_configured: true`. FastAPI reads `.env` at import/startup, so changing the key while it runs requires a restart. The key must be set in project-root `.env`, not in the browser. If `google_key_configured` is false, the Google-model launch button is disabled intentionally. Check that the request-approval checkbox is selected before starting.

The V4 core grader/oracle and historical JSONL files are unchanged. Google provider quotas still apply. Local Node tests passed; full WSL build and live Google UI launch not verified here.
