---
source: confluence
source_id: TOI-FAQ-002
title: TOI Plus subscription & paywall — common issues
space: TOI
url: https://timesinternet.atlassian.net/wiki/spaces/TOI/pages/12350/TOI+Plus+Paywall+Billing
last_updated_at: 2026-05-03T14:00:00Z
labels: [public-support, billing, subscription, paywall]
---

# TOI Plus subscription & paywall — common issues

## Paywall persists after successful payment

Symptom: a user buys a TOI Plus annual subscription (₹1499) via the in-app
flow, the payment is confirmed by their bank, but the app continues to
show the paywall.

Root cause: the entitlement refresh used to wait for the next foreground
event after the payment receipt landed. On slow networks the refresh
silently failed and the paywall did not lift.

Status: **TOI-4530** — fixed in app version 8.3.2 (24 April 2026). Users
on v8.3.2+ should not see this. For users still on v8.3.1 or older:

1. Ask the user to update the app to v8.3.2 or later.
2. Then ask them to **Settings → Account → Restore purchase**.

If restore-purchase doesn't lift the paywall on v8.3.2+, the entitlement
record may not have been written. Escalate to billing-ops with the order ID
from their email receipt.

## Other billing edge cases

- Refund requests within 7 days are processed via the standard support form.
- Annual subscriptions (₹1499) are not pro-rated on cancellation; this is
  policy, not a bug.
