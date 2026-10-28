# Backend Schema: Citedesk

Version 0.1. This file is the single source of truth for enum values, statuses, reason codes and table names. The PRD, TRD, AppFlow and UI brief refer to these exact strings.

Database: SQLite in WAL mode with foreign keys on (`PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL;`). SQL is kept portable so a move to PostgreSQL is a small change (replace `INTEGER PRIMARY KEY AUTOINCREMENT` with `BIGSERIAL`, `TEXT` timestamps with `TIMESTAMPTZ`, JSON `TEXT` with `JSONB`).

Conventions: ids are integers; timestamps are ISO 8601 UTC strings; JSON columns hold JSON text validated by Pydantic in code; booleans are `0/1`; every table has `created_at`.

## 1. Enumerations

| Name | Values |
|---|---|
| `channel` | `web_form`, `email`, `import`, `webhook` |
| `intent` | `pricing_question`, `availability_question`, `booking_request`, `booking_change`, `cancellation`, `policy_question`, `service_question`, `complaint`, `health_or_safety`, `billing_question`, `partnership_or_sales`, `spam`, `other` |
| `urgency` | `low`, `normal`, `high`, `urgent` |
| `sentiment` | `positive`, `neutral`, `negative`, `angry` |
| `confidence` | `low`, `medium`, `high` |
| `route` | `draft_reply`, `request_details`, `escalate`, `archive` |
| `inquiry_status` | `received`, `screened`, `classified`, `routed`, `drafted`, `needs_review`, `escalated`, `approved`, `rejected`, `exported`, `resolved`, `archived`, `failed` |
| `reason_code` (escalation) | `HEALTH_SAFETY`, `COMPLAINT`, `REFUND_OR_DISPUTE`, `LEGAL_THREAT`, `POLICY_EXCEPTION_REQUEST`, `INJECTION_SUSPECTED`, `LOW_CONFIDENCE`, `NOT_IN_KNOWLEDGE_BASE`, `UNVERIFIED_FIGURE`, `MANUAL` |
| `check_code` | `FIGURES_GROUNDED`, `NO_COMMITMENT`, `CLAIMS_HAVE_SOURCES`, `STRUCTURE`, `NO_INJECTION_ECHO`, `ADDRESSES_ASK` |
| `draft_kind` | `reply`, `request_details`, `holding_reply` |
| `draft_status` | `ready`, `blocked`, `approved`, `rejected`, `superseded` |
| `decision` | `approve`, `edit_approve`, `reject`, `escalate`, `resolve` |
| `service_type` | `emergency_repair`, `drain_cleaning`, `leak_repair`, `sewer_line_repair`, `water_heater`, `fixture_installation`, `inspection`, `other`, `unknown` |
| `property_type` | `house`, `apartment`, `commercial`, `other`, `unknown` |
| `stage` | `screen`, `understand`, `route`, `retrieve`, `draft`, `check` |

## 2. Required fields per intent (kept in code, shown here for reference)

| Intent | Required for `request_details` logic |
|---|---|
| `booking_request` | `service_type`, `start_date` (the preferred visit date), `property_type`, `address_area` |
| `booking_change` | `start_date` (the new date), and a way to find the booking (`booking_reference` or sender email match) |
| `availability_question` | `service_type`, `start_date` |
| `cancellation` | `booking_reference` or sender email match |
| all others | none |

## 3. Tables

```sql
-- db/migrations/0001_init.sql

CREATE TABLE schema_migrations (
  version     INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,
  applied_at  TEXT NOT NULL
);

CREATE TABLE inquiries (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  external_id     TEXT,                       -- id from the source system, if any
  channel         TEXT NOT NULL CHECK (channel IN ('web_form','email','import','webhook')),
  received_at     TEXT NOT NULL,
  sender_name     TEXT,
  sender_email    TEXT,
  subject         TEXT,
  body            TEXT NOT NULL,              -- sensitive values already masked
  thread_id       TEXT,
  duplicate_of    INTEGER REFERENCES inquiries(id),
  status          TEXT NOT NULL DEFAULT 'received'
                  CHECK (status IN ('received','screened','classified','routed','drafted','needs_review',
                                    'escalated','approved','rejected','exported','resolved','archived','failed')),
  route           TEXT CHECK (route IN ('draft_reply','request_details','escalate','archive')),
  urgency         TEXT CHECK (urgency IN ('low','normal','high','urgent')),
  primary_intent  TEXT,                       -- copied from classification for fast filtering
  failure_stage   TEXT,
  failure_message TEXT,
  is_synthetic    INTEGER NOT NULL DEFAULT 1,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX idx_inquiries_status_urgency ON inquiries(status, urgency, received_at);
CREATE INDEX idx_inquiries_sender ON inquiries(sender_email);
CREATE UNIQUE INDEX idx_inquiries_external ON inquiries(channel, external_id) WHERE external_id IS NOT NULL;

CREATE TABLE screenings (
  id                      INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id              INTEGER NOT NULL UNIQUE REFERENCES inquiries(id) ON DELETE CASCADE,
  spam_score              REAL NOT NULL,
  injection_flags         TEXT NOT NULL DEFAULT '[]',   -- JSON array of matched pattern names
  sensitive_data_masked   INTEGER NOT NULL DEFAULT 0,
  result                  TEXT NOT NULL CHECK (result IN ('clean','spam','injection_suspected')),
  created_at              TEXT NOT NULL
);

CREATE TABLE classifications (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id      INTEGER NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
  attempt         INTEGER NOT NULL DEFAULT 1,
  model           TEXT NOT NULL,
  prompt_version  TEXT NOT NULL,
  intents         TEXT NOT NULL,                -- JSON: [{"intent": "...", "confidence": "high"}]
  primary_intent  TEXT NOT NULL,
  primary_confidence TEXT NOT NULL CHECK (primary_confidence IN ('low','medium','high')),
  urgency         TEXT NOT NULL CHECK (urgency IN ('low','normal','high','urgent')),
  sentiment       TEXT NOT NULL CHECK (sentiment IN ('positive','neutral','negative','angry')),
  summary         TEXT,                         -- one internal sentence
  safety_net_hit  INTEGER NOT NULL DEFAULT 0,   -- emergency keywords raised urgency in code
  raw_response    TEXT NOT NULL,
  duration_ms     INTEGER,
  created_at      TEXT NOT NULL
);
CREATE INDEX idx_classifications_inquiry ON classifications(inquiry_id, attempt);

CREATE TABLE extractions (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id      INTEGER NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
  classification_id INTEGER NOT NULL REFERENCES classifications(id) ON DELETE CASCADE,
  fields          TEXT NOT NULL,                -- JSON, shape in section 4
  missing_fields  TEXT NOT NULL DEFAULT '[]',   -- JSON array, computed in code
  created_at      TEXT NOT NULL
);
CREATE INDEX idx_extractions_inquiry ON extractions(inquiry_id);

CREATE TABLE escalations (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id      INTEGER NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
  reason_code     TEXT NOT NULL CHECK (reason_code IN
                  ('HEALTH_SAFETY','COMPLAINT','REFUND_OR_DISPUTE','LEGAL_THREAT','POLICY_EXCEPTION_REQUEST',
                   'INJECTION_SUSPECTED','LOW_CONFIDENCE','NOT_IN_KNOWLEDGE_BASE','UNVERIFIED_FIGURE','MANUAL')),
  detail          TEXT,                         -- short, no customer text
  source          TEXT NOT NULL CHECK (source IN ('rule','safety_net','check','reviewer')),
  resolved        INTEGER NOT NULL DEFAULT 0,
  resolved_at     TEXT,
  created_at      TEXT NOT NULL
);
CREATE INDEX idx_escalations_open ON escalations(resolved, inquiry_id);

CREATE TABLE retrievals (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id      INTEGER NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
  question        TEXT NOT NULL,                -- the standalone question sent to the knowledge base
  declined        INTEGER NOT NULL DEFAULT 0,
  kb_answer       TEXT,
  sources         TEXT NOT NULL DEFAULT '[]',   -- JSON: [{"file","section","page","text"}]
  duration_ms     INTEGER,
  created_at      TEXT NOT NULL
);
CREATE INDEX idx_retrievals_inquiry ON retrievals(inquiry_id);

CREATE TABLE drafts (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id      INTEGER NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
  version         INTEGER NOT NULL DEFAULT 1,
  kind            TEXT NOT NULL CHECK (kind IN ('reply','request_details','holding_reply')),
  subject         TEXT,
  body            TEXT NOT NULL,
  claims          TEXT NOT NULL DEFAULT '[]',   -- JSON: [{"text","source_index"}], internal
  model           TEXT NOT NULL,
  prompt_version  TEXT NOT NULL,
  guidance        TEXT,                         -- reviewer guidance used for a redraft
  status          TEXT NOT NULL DEFAULT 'ready'
                  CHECK (status IN ('ready','blocked','approved','rejected','superseded')),
  duration_ms     INTEGER,
  created_at      TEXT NOT NULL,
  UNIQUE (inquiry_id, version)
);
CREATE INDEX idx_drafts_inquiry ON drafts(inquiry_id, version);

CREATE TABLE draft_checks (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id        INTEGER NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
  check_code      TEXT NOT NULL CHECK (check_code IN
                  ('FIGURES_GROUNDED','NO_COMMITMENT','CLAIMS_HAVE_SOURCES','STRUCTURE','NO_INJECTION_ECHO','ADDRESSES_ASK')),
  blocking        INTEGER NOT NULL,
  passed          INTEGER NOT NULL,
  detail          TEXT,                         -- JSON: e.g. {"ungrounded":["$85"],"derived":["$170"]}
  created_at      TEXT NOT NULL,
  UNIQUE (draft_id, check_code)
);

CREATE TABLE reviews (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id      INTEGER NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
  draft_id        INTEGER REFERENCES drafts(id) ON DELETE SET NULL,
  decision        TEXT NOT NULL CHECK (decision IN ('approve','edit_approve','reject','escalate','resolve')),
  edited_body     TEXT,
  reason          TEXT,
  reviewer        TEXT NOT NULL DEFAULT 'local',
  review_seconds  INTEGER,                      -- time from opening detail view to decision
  created_at      TEXT NOT NULL
);
CREATE INDEX idx_reviews_inquiry ON reviews(inquiry_id, created_at);

CREATE TABLE exports (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id        INTEGER NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
  method          TEXT NOT NULL CHECK (method IN ('copy','mail_draft')),
  external_ref    TEXT,                         -- id of a mail draft, never a sent message
  created_at      TEXT NOT NULL
);

CREATE TABLE audit_events (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id      INTEGER REFERENCES inquiries(id) ON DELETE CASCADE,
  event_type      TEXT NOT NULL,                -- stage_started, stage_finished, stage_failed, route_decided, check_failed, review_recorded, status_changed
  stage           TEXT,
  from_status     TEXT,
  to_status       TEXT,
  payload         TEXT NOT NULL DEFAULT '{}',   -- JSON, ids and codes only; never message or draft text
  request_id      TEXT,
  duration_ms     INTEGER,
  created_at      TEXT NOT NULL
);
CREATE INDEX idx_audit_inquiry ON audit_events(inquiry_id, created_at);

CREATE TABLE settings (
  key             TEXT PRIMARY KEY,
  value           TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
```

## 4. JSON shapes

**`classifications.intents`**
```json
[{"intent": "booking_request", "confidence": "high"}, {"intent": "pricing_question", "confidence": "medium"}]
```

**`classifications.raw_response`** is the model's accepted reply exactly as it came (a JSON object). Besides the values copied into the columns above it holds `summary`, `sentiment`, `escalation_signals` (the codes the model flagged: `REFUND_OR_DISPUTE`, `LEGAL_THREAT`, `POLICY_EXCEPTION_REQUEST`) and the model's own `urgency` before the emergency net. The route stage reads `escalation_signals` from here (D-041).

**`extractions.fields`** (every key present; unknown values are `null` or `"unknown"`)
```json
{
  "service_type": "drain_cleaning",
  "start_date": "2026-12-14",
  "property_type": "house",
  "address_area": "Alderbrook Heights",
  "preferred_contact": "email",
  "booking_reference": null,
  "dates_as_written": "Monday the 14th, mornings are best"
}
```
Dates are normalized to ISO format only when unambiguous; otherwise `null` with the original wording kept in `dates_as_written`.

**`retrievals.sources`**
```json
[{"file": "pricing.md", "section": "Pricing > Drain cleaning", "page": null, "text": "..."}]
```

**`draft_checks.detail`** examples
```json
{"ungrounded": ["$85"], "derived": ["$170"], "grounded": ["$60"]}
{"matched_patterns": ["you're booked"]}
```

**`audit_events.payload`** examples
```json
{"route": "escalate", "reason_codes": ["HEALTH_SAFETY"], "safety_net": true}
{"check": "FIGURES_GROUNDED", "passed": false}
```

## 5. State machine (enforced in code and covered by tests)

| From | To | Trigger |
|---|---|---|
| `received` | `screened` | screening finished |
| `received` | `failed` | screening crashed after retry |
| `screened` | `classified` | classification and extraction valid |
| `screened` | `archived` | spam threshold met with no other intent |
| `screened` | `escalated` | injection suspected, route decided before the model runs |
| `screened` | `failed` | model failed twice |
| `classified` | `routed` | route decided |
| `classified` | `failed` | route stage crashed after retry |
| `routed` | `escalated` | route is `escalate` |
| `routed` | `archived` | route is `archive` |
| `routed` | `drafted` | route is `draft_reply` or `request_details` and a draft exists |
| `routed` | `failed` | retrieval or drafting failed after retry |
| `drafted` | `needs_review` | checks finished and none blocking failed |
| `drafted` | `escalated` | a blocking check failed |
| `drafted` | `failed` | check stage crashed after retry |
| `needs_review` | `approved` | reviewer approves (with or without edits) |
| `needs_review` | `rejected` | reviewer rejects |
| `needs_review` | `escalated` | reviewer escalates |
| `approved` | `exported` | text copied or mail draft created |
| `rejected` | `drafted` | redraft requested (draft version + 1) |
| `rejected` | `resolved` | reviewer closes it without a reply |
| `escalated` | `resolved` | staff handled it outside the tool |
| `failed` | prior stage's input status | retry |

## 6. Views and queries the API needs

```sql
-- Review queue: needs attention first, then by urgency, then oldest first
SELECT i.* FROM inquiries i
WHERE i.status IN ('needs_review','escalated','failed')
ORDER BY CASE i.urgency WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
         i.received_at ASC;

-- Insights: how often drafts are approved unchanged vs edited
SELECT decision, COUNT(*) FROM reviews GROUP BY decision;

-- Median review time (compute in application code; SQLite has no median)
SELECT review_seconds FROM reviews WHERE decision IN ('approve','edit_approve');
```

## 7. Migration rules

- Files in `db/migrations/` are numbered and append-only (`0001_init.sql`, `0002_...`). Never edit an applied migration.
- `python -m citedesk.db migrate` applies pending migrations in order inside a transaction and records them in `schema_migrations`.
- A test applies all migrations to an empty database and checks the final schema against the enum lists in `models.py`, so the values in this file and in code cannot drift apart.

## 8. Evaluation data (files, not database tables)

```
eval/golden/citedesk_v1.json      golden set with labels and splits
eval/runs/<run id>.run.json     raw pipeline outputs per item, with provenance
eval/runs/<run id>.scores.json  computed metrics
eval/reports/                   Markdown reports
```

The file holds `{"header": {...}, "items": [...]}`. The header records the name, version, the reference date the messages are written as of, who wrote the set, a hash of the knowledge-base documents it was written against, and counts. Source items live in `eval/golden/src/*.json` and are merged by `python -m tools.golden build`; `eval/golden/golden.schema.json` is generated from the Pydantic models in `tools/golden.py`; `python -m tools.golden validate` checks everything below. Labelling rules are in `eval/golden/README.md`.

Golden item shape:
```json
{
  "id": "drain-slow-sink-this-week",
  "split": "heldout",
  "category": "vague_missing_details",
  "channel": "web_form",
  "sender_name": "Dana Whitfield",
  "sender_email": "dana.whitfield@example.com",
  "subject": "Kitchen sink draining slowly",
  "body": "Hi, my kitchen sink has been draining really slowly and gurgles. Can someone come out this week? How much would that be?",
  "labels": {
    "intents": ["availability_question", "pricing_question"],
    "primary_intent": "availability_question",
    "urgency": "normal",
    "fields": {"service_type": "drain_cleaning", "property_type": null, "address_area": null, "start_date": null},
    "should_escalate": false,
    "expected_reason_codes": [],
    "expected_route": "request_details",
    "answerable_from_docs": true
  },
  "evidence": [{"file": "services.md", "anchor": "To book a visit, please tell us"}],
  "notes": "'this week' is vague; should ask for a preferred date and the neighbourhood"
}
```

Additions to the original shape: `category` (one of `routine_answerable`, `multi_intent`, `vague_missing_details`, `booking_flow`, `urgent`, `safety`, `angry_complaint`, `dispute_legal`, `policy_exception`, `billing`, `partnership_sales`, `spam`, `out_of_scope`, `follow_up`, `injection`, `unanswerable`, `near_miss`, `edge`); `evidence` (list of `{file, anchor}`; required when `answerable_from_docs` is true, empty otherwise; the anchor is a phrase that must appear in that document, matched by text so chunking does not matter); optional `sender_email` (example.com only); optional `labels.contains_sensitive_data` (default false). Every `fields` object has the four core keys (`service_type`, `start_date`, `property_type`, `address_area`) and may have `booking_reference`. `expected_route` and `should_escalate` are checked against the routing rules in `TRD.md` section 4.3, applied to the labels, so a label cannot disagree with the rules.

All names, emails and phone numbers in generated data are invented (phone numbers in the 555-01xx range, emails at example.com).
