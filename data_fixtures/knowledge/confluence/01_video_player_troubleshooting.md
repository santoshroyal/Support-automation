---
source: confluence
source_id: TOI-FAQ-001
title: Video Player Troubleshooting (TOI app)
space: TOI
url: https://timesinternet.atlassian.net/wiki/spaces/TOI/pages/12345/Video+Player+Troubleshooting
last_updated_at: 2026-05-02T11:30:00Z
labels: [public-support, video, ios, android]
---

# Video Player Troubleshooting

## Known issue (May 2026)

Users on iPhone 14 / iPhone 15 running iOS 17.4 and 17.4.1 may experience the
in-article video player crashing within seconds of starting any clip. The
issue was introduced in TOI app version 8.3.1.

This is tracked as **TOI-4521** and a fix has been merged into the v8.4
release branch. v8.4 is currently in App Store Connect review and is
expected to roll out the week of 6 May 2026.

### Recommended workaround

While waiting for v8.4:

1. Tap **Settings → Video → Playback quality** and switch to **Auto (low)**.
2. If the crash persists, force-quit the app and reopen — the next playback
   uses the AVPlayer fallback path which is unaffected.

### Older Android devices

The same v8.3.1 release affected playback on Android 10 and 11 devices but
the rollback shipped in v8.3.2 (24 April 2026). Users on v8.3.2+ are not
affected.
