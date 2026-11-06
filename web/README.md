## v0.9.4: research story for a first-time judge

Research Overview now leads with a plain-language question, verified episode verdict, initial/recorded-after service map, clickable agent tool decisions and service classification errors. Incident Lab explicitly separates actual committed repair from what-if simulations; original raw trace, hash replay and reviewer status remain available in Execution Analysis. No new provider/AI summarizer is used. See `../docs/JUDGE_FIRST_IMPRESSION_v0.9.4.md`.

# Paper Lab UI (Next.js App Router)

- Custom paper design tokens: `app/tokens.css`
- Global layout, typography, responsive styles: `app/globals.css`
- Four-tab research views, forms, charts and tables: `app/page.tsx`
- Interactive orthogonal service graph (React Flow): `components/Topology.tsx`
- Typed FastAPI client: `lib/api.ts`

Install Node.js 20.9 or later, then:

```bash
npm install
npm run build
npm run dev
```

The app opens at http://localhost:3000 and fetches from FastAPI at http://127.0.0.1:8000. Override with `NEXT_PUBLIC_API_BASE` in `.env.local` if necessary. Never put an OpenRouter API key into `web/`.

Design: no animations, no gradients or pills, rectangular paper surfaces, flat typography, evidence first, accessible statuses. Benchmark Studio is disabled by design because task authoring is not implemented. No private model thoughts are displayed.

Formatting: `npm run format` (Prettier rewrites existing UI files) and `npm run format:check`.

Four active sections in v0.9: **Research Overview**, **Incident Lab**, **Control Room**, **Execution Analysis** (Explanation / Full timeline / Verification). Cross-run charts use independently regraded saved episodes; downloaded files remain supplementary. The deterministic explanation helper is `lib/episode-analysis.ts`, with `node --test tests/*.test.cjs`.
