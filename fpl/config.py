"""User settings. Override with env vars or CLI flags."""
import os

LEAGUE_ID = int(os.environ.get("FPL_LEAGUE", 478017))   # GME Fantasy League
MY_ENTRY = int(os.environ.get("FPL_ENTRY", 6144939))    # Manish's Team
