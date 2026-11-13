# Security policy

Citedesk is a demonstration project. It runs locally, uses invented data only, and is not offered as a hosted service. It has no login, so the API listens on `127.0.0.1` and must not be exposed to a network (see "Single user, one machine" in the README).

## Reporting a vulnerability

Report a suspected vulnerability privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Do not open a public issue for it.

Please include what you found, how to reproduce it, and what it lets someone do. Reports are read and answered as time allows; there is no bug bounty.

## In scope

- A code path that sends an email or message, or that approves or sends a draft without a person (the README says there is none).
- A way to make the API answer requests that are addressed to a name other than this machine's own, or to accept a change from a web page on another origin (DNS rebinding or cross-site requests).
- Message, draft or retrieved-document text that reaches a log or an audit event (these hold ids, codes and type names only).
- Model output or inquiry text that is rendered as HTML, or that is used to build a path, query or URL.
- Card or Social Security numbers that are stored or shown unmasked after screening.
- A draft that passes the blocking checks while containing a figure, link or owner-only promise that the checks are documented to stop.
- Deleted inquiry text that stays readable in the database file (D-101).
- A vulnerable dependency that is reachable from the running application.

## Known limits

The limits listed in the README under "Where it goes wrong" and "What the numbers do not say" are known and are not vulnerabilities in themselves: prompt injection is only partly stopped, the phrase-list checks miss paraphrases, any program on the machine can call the API, and the size and rate limits are per process. A new example of a listed limit is still welcome, for instance an injection wording that gets through screening and the checks.
