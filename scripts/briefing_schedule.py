"""Resolve the scheduled edition without silently changing a delayed run's slot."""
import datetime as dt
from prepare_feed import KST, SLOTS, timestamp

PREFLIGHT_CRONS = {'25 21,22 * * 0-4': [(6, 40), (7, 40)],
                   '35 23 * * 0-4': [(8, 50)],
                   '35 2,5,6,9 * * 1-5': [(11, 50), (14, 50), (15, 50), (18, 50)],
                   '5 11 * * 1-5': [(20, 20)]}
PUBLISH_CRONS = {'40 21,22 * * 0-4': [(6, 40), (7, 40)],
                 '50 23 * * 0-4': [(8, 50)],
                 '50 2,5,6,9 * * 1-5': [(11, 50), (14, 50), (15, 50), (18, 50)],
                 '20 11 * * 1-5': [(20, 20)]}


def resolve(now, cron=None, release_at=None, preflight=False):
    now = now.astimezone(KST)
    if release_at:
        release = timestamp(release_at).astimezone(KST)
        if release.weekday() >= 5 or release.time().replace(tzinfo=None) not in SLOTS:
            raise ValueError('invalid weekday publication slot')
        return release
    schedules = PREFLIGHT_CRONS if preflight else PUBLISH_CRONS
    if cron not in schedules:
        raise ValueError('explicit releaseAt or known schedule required')
    lead = dt.timedelta(minutes=15 if preflight else 0)
    candidates = []
    for offset in range(8):
        date = now.date() - dt.timedelta(days=offset)
        if date.weekday() >= 5:
            continue
        for hour, minute in schedules[cron]:
            release = dt.datetime.combine(date, dt.time(hour, minute), KST)
            if release - lead <= now:
                candidates.append(release)
    return max(candidates)


def key(release):
    return release.astimezone(KST).strftime('%Y-%m-%d-%H%M')
