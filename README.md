# Market Flow public news data

Only deliberately public briefing data, editorial policy and its publication tooling live here. The Android application source remains in the private market-flow-app repository.

The app reads morning-briefing.json. Reviewed drafts are staged at drafts/morning-briefing.json and cannot replace the live feed before releaseAt. Target publication slots are 07:30, 11:30, 15:30 and 20:00 KST on verified KOSPI trading days. Research preparation begins ten minutes before each target.

The publisher validates schema version 2, actual current-review metadata, foreign/domestic ordering and limits, short-lived intraday observations, expiry and the approved publication window. It refuses rollback, uses the latest content SHA and reads the public JSON back. GitHub and research execution can be delayed; a staged draft or a no-op workflow is not a completed publication. Do not alter asOf to disguise old research.

Read EDITORIAL_POLICY.md for the full current-source verification rules. Structural validation does not prove semantic factual accuracy; editors must actually verify current sources. Public drafts are public data, not confidential embargoed material.
