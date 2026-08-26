import os, sys

import logging

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(OUT, "_freecadcmd_ran.txt"), "w", encoding="utf-8") as f:
    f.write("freecadcmd executed this script\n")

logger.info("[TEST] script ran ok")
sys.stdout.flush()
