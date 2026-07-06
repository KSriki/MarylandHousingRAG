# Security, privacy & legal

## Security

- **Threats considered:** prompt injection via the question field (attempts to make the model drop the disclaimer or role-play a lawyer); cost-abuse (flood the LLM endpoint); malicious file at ingest time (only the maintainer ingests, so lower surface, but PDF parsing still runs untrusted-ish input).
- **Attack surface:** the public `POST /api/ask` field, and the ingestion parser.
- **Trust boundaries:** browser → nginx → FastAPI is the always-present one. The model runtime and pgvector sit on an internal docker network, not exposed.
- **§5A choices:** no user auth in v1 (public read-only advisory, no accounts) — recorded deliberately so a reviewer can challenge it. **Rate limiting** (§5.x) on `/api/ask` by IP. **Secrets management** (§5A.8): any API keys via env/`.env` not baked into images (multistage build keeps them out of layers). Injection mitigation: the grounding prompt is structurally separated from user input (XML-tagged context, user text quoted, not concatenated into instructions), and the disclaimer is appended by the *server* on the `done` event — the model cannot suppress it.

---

## Privacy

Questions may reveal a user's address or dispute details. v1 keeps this minimal: questions are **not persisted with identity**; logs store the question text and retrieval trace for debugging but **no IP-to-question linkage beyond short-lived rate-limit counters**, and PII is kept out of long-term logs. No accounts, so no stored profile. If per-user CC&R upload lands in v2, this section gets rewritten — that feature inherits a real privacy obligation.

---

## Legal / compliance considerations

This is the load-bearing section for this project. The system is explicitly designed to **avoid the unauthorized practice of law**: it provides information and citations, not advice or verdicts. Every response carries a server-appended disclaimer ("Informational only, not legal advice; consult a licensed Maryland attorney"). Source documents (Maryland statute, county code) are public records; CC&Rs ingested for v1 are only ones that are publicly recorded or the maintainer is authorized to use. **License:** intended open-source (MIT), stated so contributors know the terms. The "guidance not answer" behavior is not just product taste — it's the compliance boundary.

---
