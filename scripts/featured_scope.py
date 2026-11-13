"""Edition-scoped migration: old feed remains readable by installed 50-stock APKs."""
import datetime as dt

HUNDRED_FROM = '2026-11-13T20:10:00+09:00'


def hundred_edition(release):
    if isinstance(release, str): release = dt.datetime.fromisoformat(release)
    return release >= dt.datetime.fromisoformat(HUNDRED_FROM)


def amount(row):
    return row['tradeAmount'] if 'tradeAmount' in row else row['integratedTradeAmount']


def feed_prefix(payload):
    return 'featured-stocks-v2' if payload.get('schemaVersion') == 2 else 'featured-stocks'


def release_prefix(release):
    return 'featured-stocks-v2' if hundred_edition(release) else 'featured-stocks'


def regular_close_observation(observed, release):
    """Only the exchange closing-minute print is a regular-session close."""
    kst = dt.timezone(dt.timedelta(hours=9))
    local = observed.astimezone(kst)
    target = release.astimezone(kst)
    return local.date() == target.date() and local.hour == 15 and local.minute == 30
