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
