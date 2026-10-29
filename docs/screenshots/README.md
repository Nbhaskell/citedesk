# Screenshots and walkthrough

Every screen and state of the review UI, at desktop width (1280 px, files ending `-1280.webp`) and at
phone width (360 px, files ending `-360.webp`), plus one animated walkthrough
(`walkthrough.png`, an animated PNG: it plays in a browser or a GitHub page, and shows its first
frame anywhere else).

**All of it is demo data.** Every customer and message is invented. The drafts were written by the
real pipeline code with a *scripted* model and knowledge base (the same test doubles the test suite
uses), so the replies are the pipeline's own structure and checks, but not a language model's wording.
The footer says so on every screen.

## What is shown

| State | File (add `-1280.webp` or `-360.webp`) |
|---|---|
| **Queue** | |
| A list waiting for review, with the urgent chip and counts | `queue-list` |
| Every inquiry | `queue-all` |
| Nothing matches a search | `queue-no-results` |
| Loading | `queue-loading` |
| Citedesk can't be reached | `queue-error` |
| Nothing waiting (empty database) | `queue-empty` |
| **Inquiry** | |
| A draft waiting for review: message, understood-as, draft, checks, sources | `detail-review` |
| Approve pressed: the five-second wait with Undo | `detail-undo` |
| Reject asks why first | `detail-reject-form` |
| Blocked: a price that is not in the documents (cannot be approved) | `detail-blocked` |
| Refusal: the documents don't cover the question (no pretended sources) | `detail-refusal` |
| Escalated for safety, with markup in the name and message shown as text | `detail-escalated` |
| Still being prepared | `detail-processing` |
| Failed, with Retry | `detail-failed` |
| Rejected, asking for guidance to redraft | `detail-rejected` |
| Approved, ready to copy | `detail-approved` |
| Copied (exported) | `detail-exported` |
| Resolved | `detail-resolved` |
| Loading / can't be reached / no such inquiry | `detail-loading`, `detail-error`, `detail-not-found` |
| **Insights** | |
| Figures with their samples and the period | `insights` |
| With the time-saved estimate from the person's own number | `insights-estimate` |
| Too few approved replies to show a share | `insights-too-few` |
| No inquiries yet (empty database) | `insights-empty` |
| Loading / can't be reached | `insights-loading`, `insights-error` |
| **Settings** | |
| Before any service check | `settings` |
| After "Check again" | `settings-checked` |
| Loading / can't be reached | `settings-loading`, `settings-error` |
| **Anywhere** | |
| The keyboard shortcut list | `shortcut-list` |

## Two things to know when reading them

- In `settings-checked` the documents service reads "Not working" because the knowledge base
  (rag-project) was not running when the pictures were taken. That is the screen reporting a real
  failure honestly, not a mock-up.
- The walkthrough replaces the browser clipboard with a stand-in that accepts the text, because a
  headless browser has no clipboard. What the app does after a copy is what is shown.

## How they were made

`web/scripts/capture.mjs` drives a headless Edge or Chrome over the DevTools protocol (no packages to
install) against the running app. The in-app browser pane is too narrow for a true 1280 px picture,
so the script writes the files directly at the real width. Each full-page picture is taken with the
window grown to the page's height, so the footer sits at the bottom. Loading and error states are made
by holding or refusing the app's API requests.

```
node scripts/capture.mjs demo docs/screenshots          # every state (demo database)
node scripts/capture.mjs few docs/screenshots           # Insights with too few decisions
node scripts/capture.mjs empty docs/screenshots         # empty queue and Insights (empty database)
node scripts/capture.mjs walkthrough docs/screenshots   # the animated walkthrough
```

Run from `web/`, with the web dev server on 5174 and the API on 8100 pointing at the matching database
(the script needs the demo database for `demo` and `walkthrough`, one with only a few decisions for
`few`, and an empty one for `empty`). Set `BROWSER_PATH` if Edge is not at its usual place.
