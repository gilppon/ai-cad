import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(OUT, "_freecadcmd_ran.txt"), "w", encoding="utf-8") as f:
    f.write("freecadcmd executed this script\n")

print("[TEST] script ran ok")
sys.stdout.flush()
