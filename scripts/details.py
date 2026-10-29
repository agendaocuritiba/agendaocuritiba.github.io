#!/usr/bin/env python3
"""Separa os eventos que ainda não têm resumo e junta o texto das páginas originais deles.

Uso: python3 details.py OUT_DIR STATE_DIR RUN_DATE

Lê OUT_DIR/events.json e STATE_DIR/summaries.json e grava STATE_DIR/pending.json:
[{id, title, category, start, end, venue, sources, pages: [{source, url, description, price}]}]
Só a escrita do resumo e do preço curto fica para a IA; ela lê este arquivo e não precisa
acessar os sites. Entram só os eventos novos (firstSeen == RUN_DATE) e os que já estavam
pendentes e continuam sem resumo; eventos antigos sem resumo ficam de fora.
"""
import json, re, sys, time

import requests
from bs4 import BeautifulSoup

from collect import S, ld_json

MAX_DESC = 1500


def page_info(url):
    d = BeautifulSoup(S.get(url, timeout=30).text, "html.parser")
    desc, prices = "", []
    for j in ld_json(d):
        if not desc and isinstance(j.get("description"), str):
            desc = j["description"]
        offers = j.get("offers")
        for o in (offers if isinstance(offers, list) else [offers] if isinstance(offers, dict) else []):
            for k in ("price", "lowPrice", "highPrice"):
                if o.get(k) not in (None, ""):
                    prices.append(str(o[k]))
    for sel in ('meta[property="og:description"]', 'meta[name="description"]'):
        m = d.select_one(sel)
        if m and len(m.get("content", "")) > len(desc):
            desc = m["content"]
    body = re.sub(r"\s+", " ", (d.find("main") or d.find("article") or d.body or d).get_text(" "))
    if len(desc) < 200:  # descrição curta: complementa com o texto da página
        desc = (desc + " | " + body[:MAX_DESC]).strip(" |")
    money = sorted(set(re.findall(r"R\$\s?\d[\d.]*(?:,\d{2})?", body)))[:12]
    return {"description": BeautifulSoup(desc, "html.parser").get_text(" ")[:MAX_DESC],
            "price": ", ".join(dict.fromkeys(prices + money))}


def main():
    out, state, run = sys.argv[1:4]
    events = json.load(open(f"{out}/events.json"))
    try:
        done = json.load(open(f"{state}/summaries.json"))
    except FileNotFoundError:
        done = {}
    try:
        old = {p["id"]: p for p in json.load(open(f"{state}/pending.json"))}
    except FileNotFoundError:
        old = {}
    pending = []
    for e in events:
        if e["id"] in done or (e["firstSeen"] != run and e["id"] not in old):
            continue
        if e["id"] in old:  # já buscado numa coleta anterior e ainda sem resumo
            pending.append(old[e["id"]]); continue
        pages, seen = [], set()
        for o in e["originals"]:
            if o["source"] in seen or not o.get("url"):
                continue
            seen.add(o["source"])
            info = {"description": "", "price": o.get("price", "")}
            try:
                info = page_info(o["url"]); info["price"] = ", ".join(x for x in (o.get("price", ""), info["price"]) if x)
            except Exception as ex:
                info["error"] = f"{type(ex).__name__}"
            pages.append({"source": o["source"], "url": o["url"], **info})
            time.sleep(0.3)
        pending.append({"id": e["id"], "title": e["title"], "category": e["category"], "start": e["start"],
                        "end": e["end"], "venue": e.get("venue", ""), "sources": e["sources"], "pages": pages})
    json.dump(pending, open(f"{state}/pending.json", "w"), ensure_ascii=False, indent=1)
    print(f"{len(pending)} eventos sem resumo em {state}/pending.json")


if __name__ == "__main__":
    main()
