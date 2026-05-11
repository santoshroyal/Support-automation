---
source: confluence
source_id: NBT-FAQ-001
title: NBT app — font size and accessibility
space: NBT
url: https://timesinternet.atlassian.net/wiki/spaces/NBT/pages/33001/NBT+Font+Settings
last_updated_at: 2026-05-04T07:00:00Z
labels: [public-support, accessibility, font, nbt]
---

# NBT app — font size and accessibility

The Navbharat Times app supports four font-size presets via
**Settings → डिस्प्ले → फ़ॉन्ट साइज़**:

- छोटा (Small)
- मध्यम (Medium) — default
- बड़ा (Large)
- बहुत बड़ा (Very large)

## Known issue: setting reset after update (v4.2.0)

After upgrading from v4.1.x to v4.2.0 (released 28 April 2026), the saved
font-size preference resets to **मध्यम** (the default). For users who
previously set बड़ा or बहुत बड़ा this looks like the entire app suddenly
went to a smaller font.

Tracked as **NBT-1102** — a fix is queued for v4.3 (target 12 May 2026)
which will both restore the saved preference automatically and migrate
on-device preferences forward.

### Workaround

1. Open **Settings → डिस्प्ले → फ़ॉन्ट साइज़**.
2. Re-select the preferred preset.

This is a one-time action — once set on v4.2.0, the preference persists
across subsequent restarts (it's only the v4.1 → v4.2 upgrade path that
loses it).

## Older readers

Users above 60 — a sizeable fraction of the NBT readership — frequently
ask for बहुत बड़ा. Defaulting to बड़ा for new installs in v4.3 is being
discussed.
