# UI/UX Design Brief: Citedesk

Version 0.1. For use with the `frontend-design` and `ai-ui-patterns` skills if they are installed. Behavior comes from `APP_FLOW.md`; values and labels from `BACKEND_SCHEMA.md`.

## 1. Subject, audience and primary job

**Subject:** a review desk for customer inquiries at a small plumbing company (the fictional demo business). A person checks drafts the system wrote and decides what goes out.

**Audience:** front-desk staff and the owner. Non-technical, busy, interrupted often, handling dozens of messages a day on a laptop, sometimes on a phone.

**Primary job:** let a reviewer decide in under a minute whether a draft is right, with the evidence one click away, and never let something urgent hide in the queue.

**Second audience:** a hiring manager or business owner looking at the portfolio demo. The screens must also make the system's trustworthiness visible at a glance.

## 2. Design principles

1. **Checkability over polish.** Every claim in a draft is traceable to a source passage. The interface makes checking easy before it makes anything pretty.
2. **Urgent first, always visible.** Urgency and escalation are the loudest signals on the queue screen.
3. **The system shows its reading.** An "Understood as" panel states what the system thought the customer wanted and which details it found or is missing, so misreadings are caught.
4. **A person decides.** There is no "send automatically" anywhere. Buttons name their consequence.
5. **Honest uncertainty.** Refusals, blocked drafts and failures are designed screens, not error toasts.
6. **Calm, quick to scan.** Dense enough for a worker with a full queue, quiet enough not to add stress.

## 3. Visual direction (left open on purpose)

Choose the palette, type and layout in the design pass instead of using a default. Constraints:

- It should feel like a well-run local business's back office: warm, practical, human. Not a generic SaaS dashboard, not a developer console.
- Avoid the common generated-design defaults: cream background with a terracotta accent, near-black with a single neon accent, identical rounded cards with soft grey shadows, tracked-out all-caps labels above every heading, and arrows on every link.
- Use one place for boldness (for example how urgency is expressed in the queue) and keep the rest disciplined.
- Light theme is required; dark theme is optional. Body text at least 16px, line length under 80 characters in the draft editor.
- Status and urgency use color plus a word or icon; never color alone.
- Do not use trade clip-art clichés (wrenches and water drops everywhere). One restrained nod to the business is enough.
- Mark synthetic data in a persistent, unobtrusive footer: "Demo data. All customers and messages are invented."

## 4. Screens

### 4.1 Queue (home)

Purpose: choose what to work on next.

```
+--------------------------------------------------------------------------+
| Citedesk                               [Needs review 12] [Escalated 3] [All] |
+--------------------------------------------------------------------------+
| URGENT  Escalated   "Smell of gas in basement..."    Dana W.    4 min ago   |
| HIGH    Needs review  Complaint about late arrival    Marcus L.  1 h ago     |
| NORMAL  Needs review  Kitchen drain, how much?        Priya S.   2 h ago     |
| NORMAL  Needs details Faucet install, no date         Sam O.     3 h ago     |
| ...                                                                          |
+--------------------------------------------------------------------------+
| Demo data. All customers and messages are invented.                         |
+--------------------------------------------------------------------------+
```

Each row shows: urgency, route label in plain words (Escalated, Draft ready, Asking for details, Failed), a one-line summary, sender, age. Filters: needs review, escalated, failed, archived, all. Search box. Sort fixed: urgent first, then oldest. Header counts update live. Tab title shows the number needing attention.

States: empty ("Nothing waiting. New inquiries will appear here."), loading, error ("Can't reach Citedesk. Check that it is running on port 8100."), no results for a filter.

### 4.2 Inquiry detail (the main screen)

Purpose: verify and decide.

```
+------------------------+--------------------------------+-------------------+
| ORIGINAL MESSAGE       | UNDERSTOOD AS                  | DRAFT REPLY       |
| From Priya S., web form| Wants: availability + price    | Subject: ...      |
| 2 h ago                | Urgency: normal  Tone: neutral | Hi Priya, ...     |
| "Hi, can someone look  | Service: drain cleaning        | (editable)        |
| at the slow kitchen    | Property: house                |                   |
| sink this week? ..."   | Dates: "this week"             | CHECKS            |
|                        | Missing: preferred date, area  | Figures match: yes|
| Thread (1 earlier)     |                                | No promises: yes  |
|                        | SOURCES (2)                    |                   |
|                        | [1] pricing.md > Drains    v   | [Approve] [Edit]  |
|                        | [2] hours.md > Service area v  | [Reject] [Escalate]|
+------------------------+--------------------------------+-------------------+
```

On narrow screens the three columns become stacked sections in this order: Understood as, Draft with actions, Sources, Original message.

Required elements:
- **Original message** with sensitive-data warning when masked.
- **Understood as** panel: intents, urgency, sentiment, extracted fields, missing fields (highlighted), route with a plain-words reason ("Asking for missing details").
- **Draft** editor with the subject, body, character and word count against the limit. Claims in the draft that map to a source show a numbered marker; selecting it opens the source passage.
- **Sources** list: file, section, page, passage text expandable, with the matching phrase highlighted.
- **Checks** list: each check with pass or fail and a short reason. A failed blocking check is at the top, with the problem text highlighted in the draft.
- **Actions** with consequence-naming labels: "Approve reply", "Save edits and approve", "Reject draft…", "Escalate to owner…", "Redraft with guidance…". Primary action emphasized; destructive actions require a reason, not a confirmation dialog.
- **History** (collapsed): audit events in plain language ("Checked: all passed", "Edited by reviewer").

Special variants:
- **Escalated:** the draft area is replaced by a banner with the reason in plain words and what the customer wrote that triggered it, plus "Mark resolved". If a reference draft exists it sits collapsed and labelled "For reference, not checked for sending".
- **Blocked draft:** the draft is shown but marked "Not ready: the price $85 does not appear in the business's documents." No approve button; offer "Escalate" and "Redraft".
- **Failed:** shows the stage and reason with a Retry button.
- **Refusal (knowledge base declined):** "The documents don't cover this question." with options to write a reply manually or escalate.

### 4.3 Insights

Purpose: show whether the tool helps. Keep to a handful of figures:
- Inquiries handled, by route and decision.
- Share of drafts approved unchanged, edited, rejected.
- Median time to review.
- Escalations by reason.
- Median time from receipt to draft ready.

Every figure states its sample and period. Any estimate of time saved is labelled as an assumption and shows the assumption (minutes per inquiry without the tool, entered by the user).

### 4.4 Settings and rules

Read-mostly:
- Business facts being used (read from the fact sheet) and a link to the knowledge-base status.
- Escalation rules with on/off toggles and a short plain-words description of each.
- Style guide for drafts (greeting, sign-off, length limit).
- Model and knowledge-base status, data mode (synthetic or real).

## 5. Interaction details

- **Keyboard:** `j`/`k` move through the queue and between items; `Enter` opens; `a` approve (disabled when a blocking check failed); `e` focus the editor; `r` reject; `Esc` back. A `?` overlay lists shortcuts. Focus is visible everywhere.
- **Autosave** edits to a draft locally while typing; saved with the decision.
- **Optimistic updates** for decisions, with a visible undo for 5 seconds on approve and reject.
- **Live updates:** the queue refreshes as items finish processing, announced politely to screen readers without moving focus.
- **Processing state:** an item still being processed shows its current stage ("Reading the message", "Looking up your documents", "Writing a draft") in plain words.

## 6. Content and copy

Write for the staff member, not the system.

| Instead of | Write |
|---|---|
| `LOW_CONFIDENCE` | Not sure what the customer wants |
| `NOT_IN_KNOWLEDGE_BASE` | The documents don't cover this question |
| `UNVERIFIED_FIGURE` | A price or date in the draft isn't in your documents |
| `POLICY_EXCEPTION_REQUEST` | The draft makes a promise only you can make |
| `INJECTION_SUSPECTED` | This message tries to give instructions to the system |
| `HEALTH_SAFETY` | Mentions a gas smell, flooding or another safety risk |
| `request_details` | Asking for missing details |
| Submit | Approve reply |

Voice: plain verbs, sentence case, no apologies in error messages, say what happened and what to do next. Keep names for actions the same everywhere (the button "Approve reply" produces the confirmation "Reply approved").

Sample draft the interface should be able to display well (the price and wording are illustrative only; real drafts use values from the fact sheet and retrieved sources):

> Hi Priya, thanks for getting in touch. We do clear slow kitchen drains, and the price starts at $149. To find a time this week, could you tell us which day suits you and which neighbourhood the house is in? Once we have those, a member of our team will confirm a visit time.
>
> Warm regards,
> The team

## 7. Accessibility and device requirements

- Meets WCAG 2.1 AA contrast; focus never hidden; targets at least 44px on touch.
- Full keyboard path through queue, detail, and every action.
- Streaming or changing content announced in a polite live region; focus never stolen.
- Works at 360px width without horizontal scrolling; stacked layout on small screens.
- Respects reduced motion. Motion only shows a change the person caused (opening a source, completing an action).
- Model output is rendered as text, never as HTML.

## 8. States checklist for every screen

Empty, loading, error, refusal or blocked, success. Review them as a set; a demo viewer will see these first.

## 9. Technical notes for implementation

- React + TypeScript + Vite; API types generated from the FastAPI OpenAPI schema so the UI cannot drift from the backend.
- No UI framework requirement. Choose components that allow full control of focus and live regions.
- Component tests for the five states and the keyboard flow; one recorded walkthrough for the README.
- Port 5174 in development; API at `http://127.0.0.1:8100`.

## 10. Deliverables from the design pass

1. A short design plan: named color values, type families and roles, layout concept, principles, reviewed against this brief.
2. The built screens: Queue, Inquiry detail (all variants), Insights, Settings.
3. Screenshots of each state at desktop and phone width for the README.
