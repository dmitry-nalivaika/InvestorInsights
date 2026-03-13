# 001 — InvestorInsights Platform

> AI-powered SEC filing analysis platform with RAG chat, financial analysis engine, and Next.js frontend. Azure Cloud deployment, $50/month dev budget.

**Status**: Draft · **Version**: 3.0.0 (Spec Kit migration)

---

## Quick Navigation

| File | Purpose |
|------|---------|
| [`spec.md`](spec.md) | **WHAT & WHY** — User stories, acceptance criteria, functional requirements, success metrics |
| [`plan.md`](plan.md) | **HOW** — Architecture, tech stack, infrastructure, data flows, security, observability |
| [`data-model.md`](data-model.md) | ERD, entities, enums, JSONB schemas, Qdrant vector store |
| [`tasks.md`](tasks.md) | 10-phase breakdown, ~105 tasks (T001 → T821), story-based organization with [P] parallel markers |
| [`research.md`](research.md) | 10 key technical decisions with rationale and trade-offs |
| [`quickstart.md`](quickstart.md) | 6 validation scenarios with curl commands, mapped to phases |
| [`contracts/api-spec.md`](contracts/api-spec.md) | Full REST API contract — all endpoints, request/response shapes |
| [`checklists/requirements.md`](checklists/requirements.md) | Checkbox tracker for FR, NFR, success criteria, test coverage |

### Reference Files

| File | Origin |
|------|--------|
| [`reference/builtin-formulas.md`](reference/builtin-formulas.md) | 28 built-in financial ratios/metrics |
| [`reference/xbrl-tag-mapping.md`](reference/xbrl-tag-mapping.md) | SEC XBRL taxonomy → internal field mapping |
| [`reference/sec-filing-sections.md`](reference/sec-filing-sections.md) | 10-K / 10-Q section breakdown |
| [`reference/default-analysis-profile.md`](reference/default-analysis-profile.md) | Seed analysis profile (Warren Buffett criteria) |
| [`reference/project-structure.md`](reference/project-structure.md) | Full repo directory layout |
| [`reference/makefile.md`](reference/makefile.md) | Makefile targets for dev workflow |
| [`reference/database-schema-ddl.md`](reference/database-schema-ddl.md) | Full PostgreSQL DDL (tables, indexes, triggers) |
| [`reference/testing-strategy.md`](reference/testing-strategy.md) | Testing approach, coverage targets, fixture strategy |
| [`reference/env-config.md`](reference/env-config.md) | `.env.example` with validation rules |

---

## Project Principles

See [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) for the 7 core principles governing this project.

## Templates

Reusable templates for adding new feature specs live in [`.specify/templates/`](../../.specify/templates/).

---

## Reading Order

1. **New to the project?** → `spec.md` → `plan.md` → `data-model.md`
2. **Starting implementation?** → `tasks.md` → `quickstart.md` → `contracts/api-spec.md`
3. **Making a technical decision?** → `research.md` → `plan.md` (relevant section)
4. **Tracking progress?** → `checklists/requirements.md`
