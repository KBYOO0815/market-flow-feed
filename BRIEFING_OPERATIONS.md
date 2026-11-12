# Briefing source checks and publication recovery

The news researcher still verifies facts and stages editorial schema 2. The
server does not have an AI/news synthesis credential and never generates a
briefing from source availability or raw candidate links.

## Source evidence

`Check briefing sources` runs 15 minutes before each of the eight KST editions.
It independently checks all six source areas, with 10-second request timeouts,
at most two attempts per source, and no access-denial bypass. A failed source
does not cancel another topic. DART requests explicitly select the target date;
the response's selected date and filing count must match. A confirmed zero count
is distinct from a cached previous date, unreadable page, or HTTP error.

Run-specific results are stored at
`operations/source-checks/YYYY-MM-DD-HHMM/RUN_ID-ATTEMPT.json`, with a small
edition index at `operations/source-checks/YYYY-MM-DD-HHMM.json`.
The researcher reads `evidencePath`, checks freshness and original sources, and
records its actual candidate decisions separately in `operations/research/`.
HTTP success is not editorial coverage, fact verification, or proof of a trading
day. These flags remain false in source-check records. Source snippets/full
articles are not republished: only bounded candidate titles, URLs, response
hashes, selected DART date/count, and request diagnostics are stored.

For a manual source check, dispatch the workflow with an explicit `release_at`,
or push `requests/briefing-preflight.json` with `releaseAt`. The request must be
within 30 minutes before or after that original slot. This does not publish news.

## Publication recovery

`Publish reviewed briefing` uses `briefing_watch.py` and the original cron's
edition, even when GitHub delays a job. It reads the remote draft every 15 seconds
through the original release plus 30 minutes. Missing or invalid drafts leave
the existing feed intact while waiting for a correction. A later edition or
stale research cannot be relabelled to satisfy this run. News first published
after the target release is rejected, including during manual recovery.

Publication still uses the existing atomic publisher: root, dated edition, and
three-calendar-day retention move in one commit. The watcher confirms both root
and dated edition before reporting success. A delayed job can recognize an
already archived edition even after a newer root was published.

Outcomes are stored under
`operations/publications/YYYY-MM-DD-HHMM/RUN_ID-ATTEMPT.json`. Missing drafts
become `publication_missed`, not success. Source records, researcher failures,
and publication outcomes have separate paths and cannot overwrite one another.
Both workflows also upload local operation evidence as seven-day Actions
artifacts, including when a repository write fails. Check the Actions job status
as well as the record: killed runners may leave an initial in-progress record.

Schedules may be delayed by GitHub Actions. This update records and recovers
such delays inside the freshness window; it cannot guarantee exact scheduling
or fabricate a missing researched draft.
