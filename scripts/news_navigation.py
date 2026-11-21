"""Require and validate news navigation in the published feed."""
import json
from pathlib import Path
from market_briefing import validate_navigation

body=json.loads(Path("market-briefing.json").read_text(encoding="utf-8"))
if "navigation" not in body:
    raise ValueError("published news navigation required")
validate_navigation(body["navigation"])
print("News navigation contract valid.")
