#!/usr/bin/env python3
"""Trava de segurança da coleta diária: não publica se a coleta vier muito menor que a anterior.
Uso: python3 guard.py OUT_DIR PREV_EVENTS RUN_DATE [LIMITE=0.7]
Compara os eventos de OUT_DIR/events.json com os eventos ainda futuros da coleta anterior.
Sai com código 1 (e explica) quando a nova coleta tem menos que LIMITE × a anterior.
"""
import json, sys

out, prev_p, run = sys.argv[1:4]
limit = float(sys.argv[4]) if len(sys.argv) > 4 else 0.7
cur = [e for e in json.load(open(f"{out}/events.json")) if e["end"] >= run]
prev = [e for e in json.load(open(prev_p)) if e["end"] >= run]
cur_src, prev_src = {}, {}
for lst, acc in ((cur, cur_src), (prev, prev_src)):
    for e in lst:
        for s in e.get("sources", []):
            acc[s] = acc.get(s, 0) + 1
print(f"coleta atual: {len(cur)} eventos; anterior (ainda futuros): {len(prev)}")
for s in sorted(set(cur_src) | set(prev_src)):
    print(f"  {s}: {cur_src.get(s, 0)} (antes {prev_src.get(s, 0)})")
if prev and len(cur) < limit * len(prev):
    print(f"BLOQUEADO: a coleta tem {len(cur)} eventos, menos de {limit:.0%} dos {len(prev)} anteriores.")
    sys.exit(1)
print("OK: pode publicar")
