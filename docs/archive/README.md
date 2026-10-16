# Archive

Finished plans, reports and launch notes, kept as reference. **None of these describe the current system.** For that, read `docs/ARCHITECTURE.md` (current diagrams), `docs/GENERATION_ARCHITECTURE.md` (spec and decisions log, §17) and `CODEBASE.md`. Archived 2026-10-15.

| File | Stale (do not rely on) | Still useful for |
|---|---|---|
| `plans/single-writer.md` | Says C-Opus is the default and pipeline A is retired. The default is now D-Opus-low, and A is kept as the rollback. | Why the single-writer pipeline exists; decisions that code comments cite (compress never deletes sentences, the targeted fix and redraft rules). |
| `GENERATION_PHASE0_REPORT.md` | The plan and timings it proposed; the grounding check it assumed was removed on 2026-10-15. | The C-Opus baseline (about 23 s p50, 31 s p95) and the streaming design that Phase 2 followed. |
| `architecture/as-is.md` | Generation and retrieval sections (snapshot of 2026-10-10, before Phases 1-2 and the grounding removal). | Parts `ARCHITECTURE.md` does not cover: Chrome extension, auth, evals, deployment, observability, side model calls, and the dead-code and inconsistency lists, all with file:line evidence. |
| `launch/llm-costs.md` | The cost projection: it adds the grounding check, which no longer runs. | The method for computing cost per post from eval `runs.jsonl` files, the $39 / 300-post unit economics, and the list of costs it excludes (Zernio, Stripe, hosting, ingestion, free users). |
| `launch/publish-paywall.md` | Everything about the grounding check and repairs, and the note that `docs/` is tracked (it is gitignored again). | Publishing approval design (exact-text approval, flags, worker enforcement), migrations 010 and 011, the legal-page build settings (`CONTENDO_LEGAL_OPERATOR`, `CONTENDO_LEGAL_CONTACT_EMAIL`) and the open legal review, the verified-platforms rule. |
| `launch/production-onboarding.md` | Nothing major; it is a record of one incident (2026-10-14). | Production deployment order: migrations, Railway and Vercel settings, startup schema checks, and what was not verified live (Stripe checkout, Zernio publish). |
| `publishing-provider-evaluation.md` | "Decision pending": Zernio is in use. | The provider comparison, if Zernio is ever replaced. |
