# Brief: Promethean MDM

**From:** Zain (CEO) · **Date:** 2026-10-25

Build an agentic customer Master Data Management SaaS for businesses whose customer data is spread across 3–8 SaaS systems (POS, reservations, membership, CRM, email, e-commerce) and who have no data engineers and no Azure/Fabric tenant. Users register sources in a UI, supply credentials, and the system ingests, standardises, matches, builds explainable golden records and exports or writes back a consolidated master customer list that stays current.

Constraints:
- Hosted multi-tenant SaaS first; "deploy in your tenant" enterprise edition is a later tier.
- Runs on the Promethean stack: FastAPI, Next.js, Postgres 16, Redis, Arq, Cognito, Docker on the shared EC2 box.
- Matching on Splink 5 + DuckDB; ingestion via dlt; Claude only for mapping, rule drafting and gray-zone adjudication.
- Stable UUID master IDs across incremental runs are a hard requirement.
- No client literals in code; every secret encrypted per tenant; PII hashed at ingestion.

Start with Phase 0 of `promethean-mdm/docs/PLANNING.md`: the matching engine spike on public datasets, the cluster-registry prototype with stable IDs, and LLM gray-zone cost measurement. The knowledge base at `promethean-mdm/docs/customer-mdm-knowledge-base.md` is prior art the company must read before planning.

Budget per cycle: 4 hours wall-clock, 3 engineers in parallel. Report to me on the phone after each cycle.
