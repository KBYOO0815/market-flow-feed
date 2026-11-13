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
day. Editorial coverage remains false in source-check records. Trading-day verification is true only with the specific actual-trade corroboration described below. Source snippets/full
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


## 2026-11-13 15:50 incident and recovery changes

The researcher started at 15:44:19 KST and completed at 15:44:57 without a
new draft. The public draft/root remained 08:50 and the daily archive contained
only 07:40/08:50. No 15:50 publication operation or scheduled publisher run was
found during investigation. Source-check cron runs have also started hours late.
A cron schedule is not proof that a watcher actually began.

Before research, push `requests/briefing-run.json` with unique requestId,
mode=prepare and the original releaseAt. The request triggers the explicit-intent
workflow: independent source check and publication watcher jobs start from the
same pinned push commit. Their launch does not depend on a researched draft or
cron firing. The watcher accepts explicit RELEASE_AT; cron fallbacks now anchor
the edition to workflow created_at, not runner start time. Requests outside
release-20 through release+30 minutes are rejected. Intent/source/publication
records are distinct and never imply editorial completion.

A separate intraday recovery researcher checks original editions at +10 minutes:
12:00->11:50,15:00->14:50,16:00->15:50,19:00->18:50 KST on weekdays.
It skips an already published edition and independently researches a missing one
inside the original deadline. Both researchers must investigate all six areas,
try the independent alternatives for an unavailable source, and preserve actual
attempt/error evidence instead of ending at the first DART/KIND/calendar issue.
No fabricated source coverage or unverified news may be published.

After the regular session begins, dated positive-volume, positive-turnover
Samsung Electronics trades from official KIND and independent Naver KRX detail
can jointly verify that the target date actually traded. Both quote dates must
match today, occur within KRX trading hours (09:00–18:00, including KRX after-hours) and not be in the future. A header
date, HTTP 200, prior-day quote, zero volume or one source alone is insufficient.
This is an alternative to repeatedly fetching an annual calendar and exception
notice during an already verified trading day; pre-open calendar checks remain.
The preflight stores the actual two-source evidence and the official KIND URL.
It still never certifies news facts or editorial coverage.

For source diagnostics outside the publication window, use mode=diagnostic in
the explicit request. Results go to operations/briefing-diagnostics/<requestId>.json,
are tagged diagnostic_only/publicationEligible=false and cannot launch the
publication job or replace the original edition's source-check index. The missed
15:50 edition is not backfilled after 16:20. Continue original-cutoff facts in the
next actual briefing instead of manufacturing a past review time.
