# UI design plan (Phase 6, task 3)

Status: **for review, no UI code written.** Written against `UI_UX_DESIGN_BRIEF.md` (the brief), `APP_FLOW.md` and the `ai-ui-patterns` rules. The `frontend-design` skill is not installed in this environment, so the visual choices below are made directly from the brief's constraints. Where this plan departs from the brief or finds the backend short of it, section 2 says so.

## 1. Decisions needed before building

| # | Question | Recommendation | Why |
|---|---|---|---|
| 1 | **Undo for approve and reject** (brief 5: "visible undo for 5 seconds"). The API has no undo: `approved` only moves on to `exported`. | Delay the request by 5 seconds on the client. The row shows "Reply approved. Undo" while it waits. Flush at once if the page is hidden or closed (`fetch` with `keepalive`). | The alternative, a real undo endpoint, needs new state-machine moves and an audit story. A client-side delay is cheap, and the cost is stated: a decision is not on the server until the 5 seconds pass. |
| 2 | **Actions on a blocked draft** (brief 4.2: "offer Escalate and Redraft"). A blocked draft already means the inquiry is `escalated`; hand escalation works only from `needs_review`, and redraft only from `rejected` (D-050, D-051). | v1: a blocked item offers **Mark resolved** only, and shows the draft and the failed check for reference. Later, if wanted: allow `escalated` to `rejected` so the owner can redraft. | Matches the state machine as it stands. Two documents disagree here (brief against `BACKEND_SCHEMA.md` section 5); this follows the schema. |
| 3 | **Refusal screen** (brief 4.2: "write a reply manually"). There is no manual-reply endpoint, and copying an unapproved draft would bypass approval. | v1: the refusal screen explains, shows the holding reply labelled "For reference, not checked for sending", and offers **Mark resolved** (staff answer outside the tool). No manual reply. | Keeps rule 1 and rule 6 intact. A manual-reply path is a feature, not a screen. |
| 4 | **Settings toggles** (brief 4.4: "escalation rules with on/off toggles"). Only low-confidence escalation is a setting; the others are fixed in code. | v1: Settings is **read-only**. Rules are listed with plain-words descriptions and a note that they are fixed in code. | "The model reads and writes, code decides" (rule 2). A switch that turns off the safety rule is the wrong thing to build, and an owner changing a rule in a form is not covered by any test. |

If you accept all four, nothing in section 4 onward changes. If you decline 1, the approve and reject buttons become plain buttons with no delay.

## 2. Where the brief and the backend disagree or fall short

Small backend additions come first (step 0 of the build order), tests first, each recorded in `DECISIONS.md`.

| Brief asks for | Backend today | Plan |
|---|---|---|
| One-line summary on each queue row | `InquirySummary` has the subject but no summary; the model's summary is only inside `classification.raw_response` | Add `summary` to the list response. Until then the row shows the subject. |
| Header counts "Needs review 12, Escalated 3" and an urgent count | `GET /api/insights` has counts by status; urgent is not counted | Add `urgent_open` (urgent items in `needs_review`, `escalated` or `failed`) to the status response. |
| Model and knowledge-base status | `GET /api/status` reports both as `not_checked` | Add a short, loopback-only check of each (2 second limit, no text sent). |
| Settings screen: business facts, style limits, data mode | No endpoint | Add `GET /api/settings` (read-only): business name and contact details, `DRAFT_MAX_WORDS`, model name, data mode, the list of fixed rules. |
| Insights: "median time from receipt to draft ready", period and sample on every figure | Not computed; no period | Add `median_seconds_to_draft`, `period_start`, `period_end` to insights. Sample sizes are the counts already returned. The "time saved" estimate is entered in the browser and never stored (brief 4.3). |
| Thread: "1 earlier" | Only `duplicates` (same message linked) exists, no thread model in v1 | Show linked duplicates only. |
| Escalated variant: "what the customer wrote that triggered it" | Escalation `detail` is a fixed sentence by design (no customer text in rows) | Show the original message beside the reason; do not try to excerpt. |
| Sources: "matching phrase highlighted" | A claim's text is the model's paraphrase, not a quotation | Highlight only what code can match exactly: figures that the `FIGURES_GROUNDED` check reported as grounded, found in the passage. Claims show as numbered markers that open the passage. |
| Word limit shown in the editor | `DRAFT_MAX_WORDS` is not exposed | Comes with `GET /api/settings`. |
| Ages like "4 min ago" | Demo messages carry fixed 2026 dates, so ages will read "5 months ago" later | Show the age and keep the exact date in the tooltip and in text for screen readers. Not fixed in the UI; re-dating the demo inbox is a data decision for Phase 9. |
| Reason wording for `POLICY_EXCEPTION_REQUEST` and `INJECTION_SUSPECTED` | Each code has two origins (D-039, D-041, D-046): a screening or routing rule, or a draft check | Copy depends on the escalation's `source`. See section 7. |

## 3. Visual identity

### Idea

A well-run job desk: the queue is a tray of work tickets, one per customer, ruled lines, plain words. The single nod to the trade is the **ticket stub**: each queue row has a coloured edge band on its left, like the tab on a work order. No wrenches or drops.

### Colour (light theme only in Phase 6; dark is optional and deferred)

Contrast ratios were calculated, not estimated: text pairs need 4.5, boundaries and bands need 3.

| Role | Name | Value | Used for | Contrast |
|---|---|---|---|---|
| Page | Paper | `#F3F5F3` | background (a cool pale grey-green, not cream) | ink 13.4 |
| Surface | Sheet | `#FFFFFF` | rows, panels, editor | ink 14.7 |
| Text | Ink | `#1F2A30` | body | 13.4 on paper |
| Secondary text | Slate | `#56646C` | meta lines, ages | 5.6 on paper, 6.1 on sheet |
| Decoration | Rule | `#D5DAD7` | dividers only, never the sole boundary of a control | n/a |
| Boundary | Edge | `#7A8A93` | inputs, buttons, focus-adjacent borders | 3.3 on paper, 3.6 on sheet |
| Action | Patina | `#0D5C57` | primary buttons, links, selected tab | 7.1 on paper, 7.8 with white text |
| Action tint | Patina mist | `#DCEEEC` | selected row background | patina text 6.5 |
| Focus | Ring | `#1D5FD1` | 3px outline, 2px offset, on every focusable element | 5.3 on paper, 5.8 on sheet |
| Urgent | Signal | `#B3261E` band and tag fill, white text 6.5; tint `#FBE4E1` with `#8F1D14` text 7.3 | | band 6.0 on paper |
| High | Amber | band `#B7791F` (3.3 on paper); tint `#FCEBC4` with `#6B4500` text 7.2 | | |
| Normal | Slate blue | tint `#E3EAEE` with `#2F4655` text 8.1; band `#7A8A93` | | |
| Low | none | muted text, no band | | |
| Pass | Green | tint `#DFF1E3` with `#1B5E2F` text 6.6 | passed checks | |
| Fail | Signal tint | `#FBE4E1` with `#8F1D14` text 7.3 | failed checks | |
| Mark | Highlight | `#FFE08A` behind ink text | grounded figures in a passage, the problem text in a blocked draft | ink 11.4 |

Patina (a verdigris green) is the one accent: it nods to copper pipe without drawing it. The defaults the brief rules out are avoided: no cream with terracotta, no dark with neon, no row of identical soft-shadowed cards (panels are separated by rules, not shadows).

### Where the boldness goes: urgency

Urgency is the only loud thing on the queue.
- **Urgent rows** get an 8px solid Signal band, a filled "URGENT" tag with white text, and heavier row text. High rows get a 4px Amber band and a tinted "High" tag. Normal rows have a thin slate band and a quiet "Normal" word. Low rows have none.
- Colour is never alone: every row says the word. The band is redundant decoration.
- A **header chip** "Urgent 2" is always visible, on every screen, and filters the queue when pressed. Urgent items cannot be scrolled out of sight, which is the brief's principle 2.
- The browser tab reads "(2 urgent) Citedesk" or "(5) Citedesk" (number needing attention).

Everything else is quiet: one weight of border, no shadows, no gradients.

### Type

Self-hosted through pinned npm packages, so the app makes no request to a font service (the machine stays offline-capable and nothing leaks).
- **Interface and body:** Atkinson Hyperlegible (designed for legibility; distinct letterforms for I, l and 1, which matters for booking references and prices). 17px body, 16px minimum anywhere, 1.5 line height.
- **Customer text and the draft:** Source Serif 4, 18px, line length capped at 68 characters. Setting prose in a serif separates "words that will be sent or were sent" from interface labels, so the draft never reads as a UI string.
- **Figures** (prices, ages, counts) use tabular numerals.
- Headings: sentence case, semibold, no letter-spacing, no all-caps labels except the one "URGENT" tag.
- Both packages are confirmed when installed; the fallback stack is the system UI and Georgia/serif fonts, which meets the same sizes.

### Layout

- **Shell:** a top bar (name, Queue / Insights / Settings, urgent chip, connection state) and a footer fixed to the bottom of the viewport, always visible: "Demo data. All customers and messages are invented." Driven by `synthetic_data` from the status endpoint (shown even if the flag is missing, until the status call says otherwise).
- **Queue:** one column, max 960px, rows 64px tall at least (44px touch targets inside).
- **Detail, 1100px and up:** three columns as in the brief (message, understood-as with sources, draft with checks and actions). **Under 1100px:** one column in the brief's order: Understood as, Draft and actions, Sources, Original message, with a "Jump to the original message" link at the top because reading the original last is slow on a phone.
- 360px width: no horizontal scroll; actions become a full-width stack; the sticky bottom bar holds the primary action only.
- Motion: opening a source, completing an action, and the 5-second undo bar. Nothing else moves. Under `prefers-reduced-motion` these become instant.

## 4. Screens

Every screen is designed in these five states and reviewed as a set. Where a screen has no model answer to refuse, the "refusal" slot is its honest-uncertainty state.

### 4.1 Queue (`/`)

Data: `GET /api/inquiries` (filters `status`, `route`, `urgency`, `q`; cursor paging), `GET /api/insights` for header counts, polled every 5 seconds while the tab is visible.

Row: urgency band and tag, a plain-words state ("Draft ready", "Asking for details", "Escalated", "Failed", "Being read…"), summary (subject until `summary` exists), sender, age. One link per row; the whole row is the target.

Filters as tabs: Needs review (default), Escalated, Failed, Archived, All; search box (200 characters, sent as `q`).

| State | What the person sees |
|---|---|
| Empty | "Nothing waiting. New inquiries will appear here." |
| Loading | Six placeholder rows, no spinner text; announced once as "Loading the queue" |
| Error | "Can't reach Citedesk. Check that it is running on port 8100." with the request id if there is one, and Retry |
| No results (the honest-uncertainty state) | "No inquiries match this filter." with "Show all" |
| Success | Rows, newest changes announced politely ("2 new inquiries"), focus untouched |

### 4.2 Inquiry detail (`/inquiries/:id`)

Data: `GET /api/inquiries/{id}`; decisions return the updated detail. The page picks one **variant** from the data, in this order:

| Condition | Variant |
|---|---|
| status `received` to `drafted` | **Processing**: plain-words stage ("Checking the message", "Reading the message", "Deciding what to do", "Looking up your documents" or "Writing a draft" (by whether retrievals exist), "Checking the draft"); polls every 2 seconds |
| `failed` | **Failed**: stage and short reason, **Retry** (`reprocess`) |
| `escalated` with a `blocked` latest draft | **Blocked**: draft shown with "Not ready: …" and the problem text marked; no approve button |
| `escalated` with `NOT_IN_KNOWLEDGE_BASE` | **Refusal**: "The documents don't cover this question." plus the holding reply for reference |
| `escalated` otherwise | **Escalated**: banner with the reason in plain words and the original message; any draft collapsed as "For reference, not checked for sending"; **Mark resolved** |
| `needs_review` | **Review**: draft editable, checks, sources, actions. Label "Draft ready" (route `draft_reply`) or "Asking for details" (`request_details`) |
| `rejected` | **Rejected**: inline panel with guidance and **Redraft**, or **Close without a reply** |
| `approved` | **Approved**: the final text and **Copy reply** (records the copy, status becomes `exported`); line "Nothing is sent from Citedesk. Paste this into your email." |
| `exported`, `resolved`, `archived` | **Closed**: read-only, with history |

Panels (all variants share them):
- **Original message**: subject, sender, channel, age, body as plain text with line breaks kept; a warning bar if screening masked a card number; a note if it was linked as a duplicate.
- **Understood as**: intents (primary first), urgency, tone, fields found, **missing fields** highlighted with the question the draft will ask, route in plain words with the reason, and the escalation reasons. This is the panel that makes misreadings visible (principle 3).
- **Draft**: subject, body in a text area (the editor), live word count against the limit, a note "Edits are not re-checked; you are the check" (D-050). Claims appear beneath as numbered markers, each opening its source. A failed check marks its problem text in the draft by splitting the text into segments (never HTML).
- **Checks**: failed blocking checks first, then warnings, then passes, each with a word and an icon plus a plain sentence and, for figures, the figures named.
- **Sources**: file, section, page, passage collapsed to three lines with Expand; grounded figures marked. Zero sources says so ("No passages were used") and shows no citation markers.
- **Actions** (consequence-named): **Approve reply** / **Save edits and approve** (changes label when the text differs), **Reject draft…**, **Escalate to owner…**. Reject and Escalate open an inline panel under the buttons asking for a required reason or note; there is no confirmation dialog (brief). Approve is absent, not disabled, when a blocking check failed.
- **History** collapsed: audit events in plain language ("Checked: all passed", "Edited by reviewer"); built from status and event types only.

| State | What the person sees |
|---|---|
| Empty | Not applicable (an unknown id is "No inquiry has that number." with a link to the queue) |
| Loading | Skeleton panels with the three-column shape |
| Error | The error panel as in the queue; a failed decision keeps the typed edit and reason and says what happened |
| Refusal / blocked | The two variants above, designed as full screens |
| Success | "Reply approved" in a polite live region, undo bar for 5 seconds, then **Copy reply** |

### 4.3 Insights (`/insights`)

Data: `GET /api/insights` (plus the additions in section 2). Figures in plain tables, a bar where a share helps: handled by route and by decision, approved unchanged / edited / rejected shares, median review time, median time to draft, escalations by reason (plain words). Every figure carries its sample ("of 41 reviewed") and the period. The time-saved estimate is an input labelled "Minutes per inquiry without the tool (your assumption)", kept in the browser only, and the result is labelled "Estimate based on your assumption".

| State | What the person sees |
|---|---|
| Empty | "No inquiries yet." |
| Loading | Placeholder figures |
| Error | As the queue |
| Too little data (honest uncertainty) | Shares are replaced by "Too few reviews to show a share (4 so far)" below 10 decisions |
| Success | The figures |

### 4.4 Settings (`/settings`), read-only in v1

Data: `GET /api/settings`, `GET /api/status`. Business facts in use; draft style limits (greeting, sign-off, word limit); the escalation rules as a list with a plain sentence each and the note "These rules are fixed in code and cannot be switched off here"; model and knowledge-base status with a **Check again** button; data mode (synthetic or real); and a switch for **keyboard shortcuts** (the one setting, stored in the browser, section 5).

| State | What the person sees |
|---|---|
| Empty | Not applicable |
| Loading | Placeholder rows |
| Error | As the queue |
| Status unknown (honest uncertainty) | "Couldn't check the model" / "Couldn't check the documents" rather than a green tick |
| Success | The list |

## 5. Interaction

**Keyboard.** `j`/`k` move through the queue and between items, `Enter` opens, `a` approve, `e` edit, `r` reject, `x` escalate, `Esc` back, `?` the shortcut list. Single-key shortcuts are off while any text field has focus, and the Settings switch turns them off entirely (WCAG 2.1.4, character key shortcuts). `a` does nothing when approving is not possible. The full path queue to approved reply is: `j`, `Enter`, `a`, wait or `Enter` on undo-free path, `Tab` to Copy reply. A skip link jumps to the main content. Focus is always visible (Ring); opening a detail moves focus to its heading; closing returns it to the row it came from.

**Live regions.** One polite region for "2 new inquiries", "Reply approved", "Copied. Nothing was sent." and stage changes on a processing item. An assertive region only for errors that stop a decision. Focus is never moved by an update.

**Updates.** Polling, not websockets: 5 seconds for the queue, 2 seconds for a processing item, paused while the tab is hidden. A failed poll shows "Connection lost. Retrying." in the top bar and keeps the last data.

**Drafts.** The edit is saved in the browser while typing (keyed by draft id, discarded when a decision lands or the draft is replaced) and sent with the decision. `review_seconds` counts from opening the detail page and is capped at the API's limit.

**Undo.** As decision 1: approve and reject wait 5 seconds, visibly, then send. A failed send puts the item back with the typed text and an error, not a silent loss.

**Redraft.** After a rejection the inline panel asks for guidance (required, 500 characters) and shows "Writing a new draft… this can take up to a minute" while the request runs; on a model failure it says nothing was changed and offers to try again (D-051).

## 6. Safe rendering and privacy

- Model output, customer text and source passages are rendered as text through React's normal escaping. `dangerouslySetInnerHTML` is banned by lint (error), and a test renders a message full of markup and checks no element is created from it.
- Highlights are built by splitting a string into segments in code, never by inserting markup.
- No message or draft text in URLs: routes use ids only; the search box value goes to the API as a query parameter and is not written to the address bar.
- No message or draft text in console output or error reports. The error boundary shows a request id and a fixed sentence.
- Browser storage holds only: the shortcut switch, the time-saved assumption, and unsent edits (removed when a decision lands).
- The page makes requests to its own origin only. In development Vite serves on 5174 and proxies `/api` to 127.0.0.1:8100, so the API needs no cross-origin permission. How the built UI is served for the demo (FastAPI static files or a separate server) is a Phase 8 decision.

## 7. Copy

Voice: plain verbs, sentence case, no apologies, say what happened and what to do next. One name per action everywhere. Brief section 6 is kept as written; the rest are proposals to review.

**Reasons** (escalation reason, by origin where it matters):

| Code (source) | Words |
|---|---|
| `HEALTH_SAFETY` | Mentions a gas smell, flooding or another safety risk |
| `COMPLAINT` | The customer is unhappy with our service |
| `REFUND_OR_DISPUTE` | Asks for money back or disputes a charge |
| `LEGAL_THREAT` | Mentions a lawyer, a lawsuit or a formal complaint |
| `POLICY_EXCEPTION_REQUEST` (rule, model) | Asks for an exception only you can grant |
| `POLICY_EXCEPTION_REQUEST` (check) | The draft makes a promise only you can make |
| `INJECTION_SUSPECTED` (rule) | This message tries to give instructions to the system |
| `INJECTION_SUSPECTED` (check) | The draft repeats instructions or contains a link that isn't in your documents |
| `LOW_CONFIDENCE` | Not sure what the customer wants |
| `NOT_IN_KNOWLEDGE_BASE` | The documents don't cover this question |
| `UNVERIFIED_FIGURE` | A price or date in the draft isn't in your documents |
| `MANUAL` | Sent to you by a reviewer |

**Checks:** `FIGURES_GROUNDED` "Prices and dates match your documents"; `NO_COMMITMENT` "No promises only you can make"; `CLAIMS_HAVE_SOURCES` "Every fact points to a passage"; `STRUCTURE` "Reads like a reply (greeting, sign-off, length)"; `NO_INJECTION_ECHO` "No copied instructions or unknown links". `ADDRESSES_ASK` is not implemented and is not shown.

**States and routes:** `draft_reply` "Draft ready", `request_details` "Asking for details", `escalate` "Escalated", `archive` "Archived", `failed` "Failed at {stage}", `rejected` "Draft rejected", `approved` "Reply approved", `exported` "Copied", `resolved` "Resolved".

**Buttons and confirmations:** Approve reply → "Reply approved"; Save edits and approve → "Reply approved with your edits"; Reject draft… → "Draft rejected"; Escalate to owner… → "Sent to the owner"; Redraft with guidance… → "New draft ready"; Mark resolved → "Marked resolved"; Copy reply → "Copied. Nothing was sent."; Retry → "Retrying from {stage}".

**Intents** in plain words for the Understood-as panel: pricing question, availability question, booking request, change to a booking, cancellation, policy question, question about our services, complaint, health or safety, billing question, partnership or sales, spam, something else.

## 8. How it is built

**Stack:** Vite, React and TypeScript (strict), React Router for three routes, plain `fetch`. No data-fetching library, no UI kit, no CSS framework: a hundred-odd lines of hooks (`useResource` with polling, `useDecision` with the undo delay), CSS custom properties for the tokens above, and CSS modules per component. Fewer dependencies means less to pin and review, and full control of focus and live regions, as the brief asks. Versions are pinned exactly with a lockfile, as D-052 did.

**API access** goes through one `ApiClient` interface (typed from `schema.d.ts`) provided by React context. Tests hand screens a fake client; nothing in the test suite touches the network.

**Folders:** `web/src/api` (generated types, client), `web/src/screens/{queue,detail,insights,settings}`, `web/src/components` (shared: `UrgencyTag`, `StatusLine`, `CheckList`, `SourceList`, `DraftEditor`, `LiveRegion`, `Footer`), `web/src/copy` (every string above in one module, so wording is reviewed in one place), `web/src/styles` (tokens).

**Tests (Vitest, Testing Library, jest-axe):** each screen has the five states as separate tests, each with an automated accessibility check; the detail screen has every variant in section 4.2; one keyboard test walks queue to approved reply to copy using only the keyboard (this is the phase's acceptance check); one test renders hostile markup. Lint rules: no `dangerouslySetInnerHTML`, no `console`.

**Build order** (one commit per step, tests with the code, not after):
0. Backend additions from section 2 (tests first, OpenAPI and types regenerated, D-053).
1. Scaffold: Vite, tokens, shell, footer, router, `ApiClient`, copy module, lint and test setup. CI runs lint, tests and build.
2. Queue.
3. Detail: Review variant, then Processing and Failed, then Escalated, Blocked, Refusal, then Rejected/Redraft and Approved/Copy.
4. Insights.
5. Settings.
6. Keyboard map, live regions, 360px pass, reduced motion; fix what the checks and a manual walk-through find.
7. Screenshots at 1280px and 360px for every state, and one walkthrough recording, taken from the running app with the in-app browser (the brief's deliverable 3).

## 9. Check against the brief

- Principles 1 to 6: checkability (sources and grounded figures one click away), urgency first (band, tag, chip, tab title), shows its reading (Understood-as with missing fields), a person decides (no send path; "Nothing is sent from Citedesk"), honest uncertainty (blocked, refusal, failed, "too few reviews", "couldn't check" are screens), calm (one accent, no shadows, one loud element).
- Section 3 constraints: body at least 16px (17), line length under 80 (68), colour never alone, no clip art, persistent synthetic-data footer, light theme.
- Section 7: contrast figures above; 44px targets; full keyboard path; live regions; 360px; reduced motion; model output as text.
- Not done in this phase on purpose: dark theme, manual reply, editable rules, a real undo endpoint.
