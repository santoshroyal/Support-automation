---
source: confluence
source_id: ET-FAQ-001
title: ET Markets — live data refresh policy
space: ET
url: https://timesinternet.atlassian.net/wiki/spaces/ET/pages/22001/ET+Markets+Live+Data
last_updated_at: 2026-05-04T08:30:00Z
labels: [public-support, et-markets, live-data]
---

# ET Markets — live data refresh policy

The ET Markets section in the ET app is **not** intended as a tick-by-tick
trading terminal. Quotes are refreshed on a 60-second cadence under normal
conditions, with best-effort refresh during high-volatility windows.

## Known issue: refresh stalls (May 2026)

Tracked as **ET-2010**. The market data caching layer in app v5.7.x is
not always flushing when an upstream quote update arrives, causing the
displayed Sensex / Nifty values to lag by 2-5 minutes during the morning
session (09:15 - 11:00 IST).

A fix is in active development; ETA second week of May 2026.

### Holding response for traders

Active traders who need sub-second quotes should be advised to use a
broker terminal — the ET app has never been positioned for live trading.
For positional / news-driven traders the 60-second policy is sufficient
and the stall is a regression, not a design choice.

## iOS home-screen widget

A watchlist-style home-screen widget was the most-upvoted iOS feature
request in Q1 2026 and is now scheduled for **v6.0** (Q3 2026). Tracked
as **ET-2015**.
