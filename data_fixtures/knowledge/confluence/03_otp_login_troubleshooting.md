---
source: confluence
source_id: TOI-FAQ-003
title: OTP / login troubleshooting
space: TOI
url: https://timesinternet.atlassian.net/wiki/spaces/TOI/pages/12360/OTP+Login+Troubleshooting
last_updated_at: 2026-04-29T09:15:00Z
labels: [public-support, login, otp, account]
---

# OTP / login troubleshooting

## SMS OTP not received

Symptom: user enters their mobile number on the login screen, the OTP
prompt appears, but no SMS arrives — even after multiple retries.

Known carrier delays:

- **Vi (formerly Vodafone Idea)**: SMS delivery to TRAI-DLT registered
  short-codes is currently delayed by 30-90 seconds for some circles.
- **JIO**: occasional bursts of 1-2 minute delays.

Tracked as **TOI-4540** — engineering is working on a fallback that retries
delivery via a secondary carrier after 45 seconds. ETA: end of May 2026.

### Workaround

- Ask the user to wait at least 90 seconds before retrying.
- If still no SMS after 3 attempts, fall back to **email OTP** (link in the
  bottom-right of the login screen).
- For corporate users behind enterprise SMS filters, advise email OTP as
  the primary path.

## Sign-in stuck after OTP

Less common: user enters a valid OTP and sees an indefinite loading spinner.
This was caused by a session-token endpoint timeout on TOI-4548 — fixed
in v8.3.2.
