---
source: confluence
source_id: TOI-FAQ-004
title: Audio briefings — feature overview & known issues
space: TOI
url: https://timesinternet.atlassian.net/wiki/spaces/TOI/pages/12370/Audio+Briefings
last_updated_at: 2026-05-01T18:00:00Z
labels: [public-support, audio, ios, feature]
---

# Audio briefings — feature overview & known issues

The audio briefings feature was launched in TOI app v8.3 (March 2026). It
generates a 5-minute audio summary of the day's top stories, refreshed
twice daily (morning + evening editions).

## Known issue: playback hangs on iOS 17.4+

Tracked as **TOI-4550**. On iPhones running iOS 17.4 or 17.4.1 with TOI
app v8.3.x, tapping the play button on an audio briefing displays the
spinning playback indicator indefinitely without audio starting.

The root cause is an AVAudioSession activation race that surfaces under
iOS 17.4's stricter background-audio policy.

A fix is queued for v8.4 (rolling out the week of 6 May 2026).

### Workaround for users

1. Tap the briefing card to dismiss the failed attempt.
2. Pull down to refresh the home feed.
3. Re-tap the briefing — the second attempt almost always succeeds.

## Positive feedback

The feature has received strong positive ratings — the morning briefing in
particular sees daily completion rates above 60% on Android, where the
feature is unaffected by the iOS issue above.
