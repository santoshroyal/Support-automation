# Systemd units — production deployment

Eight units run the system unattended on a Linux VM:

| Unit | Kind | Trigger |
|---|---|---|
| `support-automation-api.service` | always-on | systemd boot |
| `support-automation-ingest.{service,timer}` | one-shot cron | every 15 min |
| `support-automation-classify.{service,timer}` | one-shot cron | every 15 min |
| `support-automation-knowledge-sync.{service,timer}` | one-shot cron | every 90 min |
| `support-automation-draft.{service,timer}` | one-shot cron | every 15 min |
| `support-automation-spike.{service,timer}` | one-shot cron | every 30 min |
| `support-automation-digest-hourly.{service,timer}` | one-shot cron | every hour |
| `support-automation-digest-daily.{service,timer}` | one-shot cron | 08:00 IST |
| `support-automation-failure@.service` | template | triggered by `OnFailure=` from any of the above |

## One-time setup on the VM

```bash
# 1. Create the service user and the code directory.
sudo useradd --system --home /opt/support-automation --shell /usr/sbin/nologin support-automation
sudo install -d -o support-automation -g support-automation /opt/support-automation

# 2. Clone the repo and build everything (Python + SPA).
sudo -u support-automation bash -c '
    git clone https://github.com/santoshroyal/Support-automation.git /opt/support-automation
    cd /opt/support-automation
    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"
    cd web_ui && npm ci && npm run build
'

# 3. Put the env file in place. Edit before saving — at minimum, set
#    SUPPORT_AUTOMATION_DATABASE_URL.
sudo install -d -m 750 -o support-automation -g support-automation /etc/support-automation
sudo install -m 640 -o support-automation -g support-automation \
    /opt/support-automation/deployment/systemd/env.example \
    /etc/support-automation/env
sudo $EDITOR /etc/support-automation/env

# 4. Apply the Alembic migrations.
sudo -u support-automation bash -c '
    cd /opt/support-automation
    export $(grep -v "^#" /etc/support-automation/env | xargs)
    .venv/bin/alembic upgrade head
'

# 5. Install + enable the units.
sudo cp deployment/systemd/*.service deployment/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now \
    support-automation-api.service \
    support-automation-ingest.timer \
    support-automation-classify.timer \
    support-automation-knowledge-sync.timer \
    support-automation-draft.timer \
    support-automation-spike.timer \
    support-automation-digest-hourly.timer \
    support-automation-digest-daily.timer
```

## Day-to-day commands

| Goal | Command |
|---|---|
| See what's scheduled and when each next runs | `systemctl list-timers 'support-automation-*'` |
| Run one cron manually right now | `sudo systemctl start support-automation-ingest.service` |
| Tail the API logs | `journalctl -u support-automation-api.service -f` |
| See the last 100 lines from a cron job | `journalctl -u support-automation-draft.service -n 100 --no-pager` |
| Find all failures in the last 24 h | `journalctl -t support-automation-failure --since "24 hours ago"` |
| Restart the API | `sudo systemctl restart support-automation-api.service` |
| Disable a single cron temporarily | `sudo systemctl disable --now support-automation-spike.timer` |
| Re-read the env file (after edits) | `sudo systemctl daemon-reload && sudo systemctl restart support-automation-api.service` |

## Schedule offsets — why each cron runs at minute X/N

The cron timers are deliberately staggered so they don't all hammer
Postgres at minute 0:

| Cron | OnCalendar | First fires at |
|---|---|---|
| ingest | `*:0/15` | :00, :15, :30, :45 |
| classify | `*:5/15` | :05, :20, :35, :50 |
| draft | `*:10/15` | :10, :25, :40, :55 |
| spike | `*:15/30` | :15, :45 |
| knowledge-sync | `*:10/90` | :10 (every 90 min) |
| digest-hourly | `hourly` | :00 |
| digest-daily | `08:00 Asia/Kolkata` | once a day |

## Removing everything

```bash
sudo systemctl disable --now 'support-automation-*'
sudo rm /etc/systemd/system/support-automation-*.{service,timer}
sudo systemctl daemon-reload
sudo userdel support-automation              # optional
sudo rm -rf /opt/support-automation /etc/support-automation   # only if you're sure
```

## OnFailure notification

Every cron unit declares `OnFailure=support-automation-failure@%n.service`,
which today writes a tagged line to journald: search with
`journalctl -t support-automation-failure`.

To get real alerts (email, Slack, PagerDuty), edit
`support-automation-failure@.service` and replace the `ExecStart` line
with a call to your sender of choice. Everything else stays as-is —
the template already receives `%i` (the failing unit's name).
