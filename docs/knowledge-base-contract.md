# Knowledge-base contract: rag-project `/api/ask`

What Citedesk's `RagProjectKB` adapter (Phase 5) can rely on. Recorded on 2026-10-28 against `rag-project` commit `cb4ebe0`, with the Citedesk knowledge-base documents (`universe/docs`, 8 files, 83 chunks) indexed. Everything below was observed by running it, except the error table, which comes from `rag-project/guides/api.md`.

## How it was run

`rag-project` is a separate project at its own folder. It was pointed at Citedesk's documents with a separate index so that its own `docs/` and index are untouched. From the `rag-project` folder, in PowerShell:

```powershell
$env:RAG_DOCS_DIR = "<citedesk>\universe\docs"
$env:RAG_DB_DIR   = "<citedesk>\data\kb_index"    # git-ignored
$env:RAG_LOG      = "0"                            # see "Privacy" below
$env:RAG_WATCH    = "0"                            # index only when asked
venv\Scripts\python.exe chat.py --no-browser       # serves 127.0.0.1:8000
```

With the watcher off, index (or re-index after the documents change) with `POST /api/reindex` and body `{}`. The response lists `added`, `updated`, `removed` and `warnings`.

Models in use: chat `qwen3:8b` with thinking **on** (rag-project's default), embeddings `embeddinggemma`.

## Request

`POST http://127.0.0.1:8000/api/ask`, `Content-Type: application/json`.

```json
{"question": "How much does drain cleaning cost?"}
```

| Field | Type | Notes |
|---|---|---|
| `question` | string, required | Whitespace is trimmed. 1 to 2000 characters. |
| `history` | list of `{"role": "user" or "assistant", "content": string}`, optional | Only the last 20 messages are used. |

`GET /api/status` returns what is indexed (`files`, `chunks`, `documents`, `last_sync`, `last_change`) and the options in force (`chat_model`, `embed_model`, `thinking`, `split_search`, `watching`, `auth_required`). It is a cheap health check for Citedesk's own `/api/status`.

## Response

```json
{
  "answer": "Drain cleaning for one fixture (sink, tub, shower, or toilet) starts at $149. ...",
  "sources": ["faq.md", "pricing.md"],
  "passages": [
    {"source": "faq.md", "section": "How much does drain cleaning cost?", "page": null,
     "text": "Drain cleaning for one fixture starts at $149. Main sewer line cleaning is $329.",
     "distance": 0.331, "best": true, "listed": true}
  ],
  "seconds": 8.3
}
```

| Field | Meaning |
|---|---|
| `answer` | The model's text. Untrusted: render as text only. |
| `sources` | File names listed under the answer. **Empty when rag-project judged the answer a refusal.** |
| `passages` | Every passage the model was given, best match first (4 by default). Present even when `sources` is empty. |
| `passages[].source`, `.section`, `.page`, `.text` | File, heading path, PDF page (`null` for markdown), passage text. These are enough to fill `retrievals.sources` (`file`, `section`, `page`, `text`). TRD open question 1 is answered: yes. |
| `passages[].distance` | Smaller is closer. |
| `passages[].best`, `.listed` | Closest passage; whether its file is in `sources`. |
| `seconds` | Time rag-project spent. |

Recorded examples are in `tests/fixtures/`: `rag_ask_answered.json`, `rag_ask_partial_availability.json` and `rag_ask_unrelated.json`. Each holds the request and the full response.

Errors come back as JSON with an `error` message: 400 bad request, 401 missing or wrong token (only if `RAG_API_TOKEN` is set), 403 unknown `Host`, 413 body over 100 KB, 415 not JSON, 500 failure while answering, 503 busy or daily limit (with `Retry-After`). Defaults: 30 questions per visitor per minute and 2 answers at once.

## Mapping to Citedesk

| Citedesk | rag-project |
|---|---|
| `retrievals.question` | the standalone question sent |
| `retrievals.kb_answer` | `answer` |
| `retrievals.sources` | `passages` whose `listed` is true, as `{file, section, page, text}` |
| `retrievals.duration_ms` | measure on the Citedesk side (rag-project's `seconds` excludes network and queueing) |
| `retrievals.declined` | **not a field in the response; see below** |

## Findings that affect the design

### A decline cannot be read from `sources` alone

| Observation | `sources` | What it means |
|---|---|---|
| A question unrelated to the business ("What will the weather be like tomorrow?") | `[]` | A real decline. `answer` is "I don't know." |
| "Do you service air conditioners?" (first run, before the document change below) | `["faq.md", "service-area.md"]` | The answer said "I don't know", but rag-project treated a sentence containing a number ("up to 4 units") as a partial answer and listed sources. A decline that `sources == []` would miss. |
| The same question, a few minutes later | `[]` | Same question, different outcome. The model is not deterministic. |
| "Do you have an opening next Tuesday afternoon?" | `["hours.md", "faq.md"]` | A partial answer. The text said the office is open on Tuesday afternoon, then that it cannot say whether there is an opening. Real availability is not in the documents, yet this is not a decline either. |

Implications for Phase 5, to be decided there and recorded in `DECISIONS.md`:

- The adapter must not use `sources == []` as its only decline test. Candidate rule, all in code: declined when `sources` is empty, or when the first sentence of `answer` is a refusal phrase ("I don't know" and similar).
- Availability questions need handling in code that does not depend on the knowledge base. A partial answer like the one above would read as helpful in a draft while confirming nothing.
- Because the same question can give different answers on different runs, recorded fixtures prove only that the adapter parses the format. Model behavior is measured in the evaluation, with repeated runs.

### Retrieval missed documented exclusions until the documents were restructured

Nine ad-hoc questions, one per item on the not-offered list ("Can you rewire an outlet?", "Can you fix my well pump?" and so on), were asked once each, before and after splitting "Work we do not do" into one short section per item (following rag-project's own advice that one topic per section works best):

| | Before | After |
|---|---|---|
| Exclusion passage in the top 4 | 0 of 9 | 8 of 9 |
| Answer opened with "No" | 2 of 9 | 8 of 9 |
| Answer was "I don't know" | 6 of 9 | 0 of 9 |
| Answer was a wrong "Yes" | 1 of 9 | 1 of 9 |

The remaining failure: "Can you do the plumbing at my restaurant?" still gets "Yes, we can do plumbing repairs at your restaurant", although the documents say commercial buildings are not served. The word "restaurant" does not connect to "commercial or industrial buildings". The documents were deliberately not changed to fix this one question.

Limits of this measurement: nine questions written by the developer, one run each, thinking on. It shows a direction, not a rate. These questions are not part of the golden set.

Implication: the knowledge base alone cannot be trusted to refuse out-of-scope work. Code must also act on `property_type = commercial` and on the not-offered list when routing (Phase 4), and the draft checks (Phase 5) are the last line of defence.

### Privacy

By default rag-project writes each question to its own `logs/` folder. Citedesk's questions are derived from customer messages, so run it with `RAG_LOG=0` (or `RAG_LOG_QUESTIONS=0`). This was done for the recording above, and no `logs/` folder was created.

### Speed

2 to 16 seconds per question on this machine with thinking on. A pipeline that asks one question per intent should expect tens of seconds per inquiry in the worst case.
