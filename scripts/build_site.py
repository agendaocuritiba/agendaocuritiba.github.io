#!/usr/bin/env python3
"""Gera os dados e as páginas do site público a partir de out/events.json.
Uso: python3 build_site.py OUT_DIR RUN_DATE SITE_DIR [FIRST_RUN]

Grava em SITE_DIR: data/events.json, e/<id>.html (uma página por evento, com
tags de prévia para WhatsApp e redes) e sitemap.xml.
"""
import json, sys, os, re, shutil, html
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlencode

SITE_URL = "https://dennymarcels.github.io/agendao-curitiba/"
ISSUES_URL = "https://github.com/dennymarcels/agendao-curitiba/issues"
PUBLISHERS = {"Turismo Curitiba", "Evento ON"}


SMALL = {"a","o","as","os","e","de","da","do","das","dos","em","no","na","com","para","por","ao","um","uma"}


ACRONYMS = {"MPB","DJ","DJS","UK","EUA","USA","TV","CWB","PR","SP","RJ","FAP","MON","UFPR","PUC","PUCPR","FIEP","SESI","SESC","EDM","XV","XVI","IX","II","III","IV","VI","VII","VIII","X","K-POP"}

DOW = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
MON = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def fix_caps(t):
    letters = [c for c in t if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.7:
        return t
    out = []
    for i, w in enumerate(t.split(" ")):
        lw = w.lower()
        if i and lw in SMALL:
            out.append(lw)
        elif w.strip("()[]:,.!?\"'").upper() in ACRONYMS:
            out.append(w)  # siglas curtas (MPB, DJ, UK)
        else:
            out.append(lw[:1].upper() + lw[1:])
    return " ".join(out)


def slim(e):
    links, seen = [], set()
    for o in sorted(e["originals"], key=lambda o: o["start"]):
        if o["source"] in seen or not o.get("url"):
            continue
        seen.add(o["source"]); links.append([o["source"], o["url"]])
    d = {"id": e["id"], "t": fix_caps(e["title"]), "c": e["category"], "s": e["start"], "e": e["end"],
         "h": e.get("time", ""), "v": (e.get("venue") or "").strip().rstrip("."), "f": e.get("firstSeen", ""), "L": links}
    if e.get("dates") and len(e["dates"]) > 1:
        d["d"] = e["dates"]
    if e.get("address"):
        d["a"] = e["address"]
    prices = " ".join([e.get("price", "")] + [o.get("price", "") for o in e["originals"]] + [e["title"]])
    if e.get("free") or re.search(r"gratuit|entrada franca|gr[aá]tis|\bfree\b", prices, re.I):
        d["g"] = 1
    if e.get("summary"):
        d["r"] = e["summary"]
    return d


# --- Páginas por evento -----------------------------------------------------

def short(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {MON[d.month - 1]}"


def when_text(d, run):
    """Texto de data para a prévia: 'sáb, 25 out', '25 out a 2 nov', 'até 2 nov'."""
    if d.get("d"):
        nxt = [x for x in d["d"] if x >= run]
        if len(nxt) > 1:
            return f"{len(nxt)} datas, de {short(nxt[0])} a {short(nxt[-1])}"
    if d["s"] != d["e"]:
        return f"até {short(d['e'])}" if d["s"] <= run else f"{short(d['s'])} a {short(d['e'])}"
    day = date.fromisoformat(d["s"])
    return f"{DOW[day.weekday()]}, {short(d['s'])}"


def clip(s, n):
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


def next_date(d, run):
    nxt = [x for x in d.get("d") or [] if x >= run]
    return nxt[0] if nxt else max(d["s"], run)


def cal_times(d, run):
    """Início e fim (2h) no horário de Curitiba, ou None quando não há horário."""
    day = next_date(d, run)
    m = re.match(r"(\d{1,2})h(\d{2})?", d.get("h") or "")
    if not m or int(m.group(1)) > 23:
        return day, None, None
    st = datetime.fromisoformat(day) + timedelta(hours=int(m.group(1)), minutes=int(m.group(2) or 0))
    return day, st, st + timedelta(hours=2)


def ics(d, run):
    day, st, en = cal_times(d, run)
    esc = lambda s: re.sub(r"([\\,;])", r"\\\1", str(s or "")).replace("\n", "\\n")
    url = f"{SITE_URL}e/{d['id']}.html"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Agendao Curitiba//PT", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "BEGIN:VEVENT", f"UID:{d['id']}@agendao-curitiba", f"DTSTAMP:{run.replace('-', '')}T090000Z"]
    if st:
        lines += [f"DTSTART;TZID=America/Sao_Paulo:{st:%Y%m%dT%H%M%S}", f"DTEND;TZID=America/Sao_Paulo:{en:%Y%m%dT%H%M%S}"]
    else:
        nd = date.fromisoformat(day) + timedelta(days=1)
        lines += [f"DTSTART;VALUE=DATE:{day.replace('-', '')}", f"DTEND;VALUE=DATE:{nd:%Y%m%d}"]
    lines += ["SUMMARY:" + esc(d["t"]), "LOCATION:" + esc(", ".join(x for x in [d["v"], d.get("a"), "Curitiba - PR"] if x)),
              "DESCRIPTION:" + esc(((d.get("r") or "") + "\n\n" + url).strip()), "URL:" + url, "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def cal_links(d, run):
    day, st, en = cal_times(d, run)
    loc = ", ".join(x for x in [d["v"], d.get("a"), "Curitiba - PR"] if x)
    details = ((d.get("r") or "") + "\n\n" + f"{SITE_URL}e/{d['id']}.html").strip()
    if st:
        gd, os_, oe, allday = f"{st:%Y%m%dT%H%M%S}/{en:%Y%m%dT%H%M%S}", f"{st:%Y-%m-%dT%H:%M:%S}", f"{en:%Y-%m-%dT%H:%M:%S}", "false"
    else:
        nd = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        gd, os_, oe, allday = day.replace("-", "") + "/" + nd.replace("-", ""), day, nd, "true"
    g = urlencode({"action": "TEMPLATE", "text": d["t"], "details": details, "location": loc, "ctz": "America/Sao_Paulo", "dates": gd})
    o = urlencode({"path": "/calendar/action/compose", "rru": "addevent", "subject": d["t"], "body": details, "location": loc,
                   "startdt": os_, "enddt": oe, "allday": allday})
    return [("Google Agenda", "https://calendar.google.com/calendar/render?" + g), ("Apple / iPhone", f"{d['id']}.ics"),
            ("Outlook", "https://outlook.live.com/calendar/0/deeplink/compose?" + o)]


def event_page(d, img, run):
    esc = lambda s: html.escape(str(s or ""), quote=True)
    url = f"{SITE_URL}e/{d['id']}.html"
    when = when_text(d, run)
    hour = d["h"] if re.search(r"\d", d.get("h") or "") else ""
    line = " · ".join(x for x in [when, hour, d["v"]] if x)
    desc = clip(f"{line}. {d['r']}" if d.get("r") else f"{line}. {d['c']} em Curitiba.", 200)
    image = img if img and img.startswith("https://") else SITE_URL + "og.png"
    pubs = [l for l in d["L"] if l[0] in PUBLISHERS] or d["L"]
    links = "\n".join(f'      <a class="go" href="{esc(u)}" target="_blank" rel="noopener">{esc(s)}</a>' for s, u in pubs)
    maps = ""
    if d["v"] and not re.match(r"(?i)^local a definir$", d["v"]):
        q = ", ".join(x for x in [d["v"], d.get("a"), "Curitiba PR"] if x)
        maps = f' · <a href="https://www.google.com/maps/search/?api=1&amp;query={esc(quote(q))}" target="_blank" rel="noopener">ver no mapa</a>'
    cal = "\n".join(f'      <a class="ca" href="{esc(u)}"' + ('' if u.endswith('.ics') else ' target="_blank" rel="noopener"') + f'>{esc(n)}</a>' for n, u in cal_links(d, run))
    dates = ""
    if d.get("d"):
        nxt = [x for x in d["d"] if x >= run]
        if len(nxt) > 1:
            dates = '<p class="dates">Datas: ' + esc(", ".join(short(x) for x in nxt)) + "</p>"
    ld = {"@context": "https://schema.org", "@type": "Event", "name": d["t"], "startDate": d["s"], "endDate": d["e"],
          "url": url, "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
          "location": {"@type": "Place", "name": d["v"] or "Curitiba",
                       "address": {"@type": "PostalAddress", "streetAddress": d.get("a", ""), "addressLocality": "Curitiba",
                                   "addressRegion": "PR", "addressCountry": "BR"}}}
    if d.get("r"):
        ld["description"] = d["r"]
    if img and img.startswith("https://"):
        ld["image"] = [img]
    if d.get("g"):
        ld["isAccessibleForFree"] = True
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    title = esc(d["t"])
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Agendão Curitiba</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:locale" content="pt_BR">
<meta property="og:site_name" content="Agendão Curitiba">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{esc(image)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#1f5d3f">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="../evento.css">
<script type="application/ld+json">{ld_json}</script>
</head>
<body>
<main class="wrap">
  <p class="home"><a href="../">Agendão <span>Curitiba</span></a></p>
  <article class="ev">
    <p class="cat">{esc(d['c'])}{' · <b>Gratuito</b>' if d.get('g') else ''}</p>
    <h1>{title}</h1>
    <p class="meta"><b>{esc(when[:1].upper() + when[1:])}</b>{' · ' + esc(hour) if hour else ''}</p>
    <p class="meta">{esc(d['v'] or 'Local a definir')}{(' · ' + esc(d['a'])) if d.get('a') else ''}{maps}</p>
    {dates}
    {'<p class="desc">' + esc(d['r']) + '</p>' if d.get('r') else ''}
    <p class="lbl">Mais informações e ingressos</p>
    <div class="acts">
{links}
    </div>
    <p class="lbl">Adicionar à agenda</p>
    <div class="acts">
{cal}
    </div>
    <p class="back"><a href="../#{esc(d['id'])}">Ver na agenda completa</a></p>
  </article>
  <footer>
    <p>Datas, horários e preços podem mudar: confira sempre a página oficial antes de sair de casa. O Agendão Curitiba é um agregador independente, sem ligação com os sites citados. Encontrou um erro? Abra um aviso na <a href="{ISSUES_URL}" rel="noopener">página de issues do projeto</a>.</p>
  </footer>
</main>
</body>
</html>
"""


def sitemap(run, ids):
    rows = [f"  <url><loc>{SITE_URL}</loc><lastmod>{run}</lastmod><changefreq>daily</changefreq></url>"]
    rows += [f"  <url><loc>{SITE_URL}e/{i}.html</loc><lastmod>{run}</lastmod></url>" for i in ids]
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n"


def main():
    out, run, site = sys.argv[1:4]
    first_run = sys.argv[4] if len(sys.argv) > 4 else ""
    events = [e for e in json.load(open(f"{out}/events.json")) if e["end"] >= run]
    sp = f"{out}/summaries.json"
    if os.path.exists(sp):  # resumos guardados por id de evento
        sm = json.load(open(sp))
        for e in events:
            if not e.get("summary") and sm.get(e["id"]):
                e["summary"] = sm[e["id"]]
    stats = json.load(open(f"{out}/stats.json"))
    os.makedirs(f"{site}/data", exist_ok=True)
    slims = [slim(e) for e in events]
    data = {"meta": {"updated": run, "horizon": stats["horizon"], "firstRun": first_run, "siteUrl": SITE_URL},
            "events": slims}
    json.dump(data, open(f"{site}/data/events.json", "w"), ensure_ascii=False, separators=(",", ":"))
    # Páginas de evento: recria a pasta para apagar as de eventos que já passaram
    shutil.rmtree(f"{site}/e", ignore_errors=True)
    os.makedirs(f"{site}/e")
    for e, d in zip(events, slims):
        with open(f"{site}/e/{d['id']}.html", "w") as f:
            f.write(event_page(d, e.get("image"), run))
        with open(f"{site}/e/{d['id']}.ics", "w", newline="") as f:
            f.write(ics(d, run))
    with open(f"{site}/sitemap.xml", "w") as f:
        f.write(sitemap(run, [d["id"] for d in slims]))
    print(len(events), "eventos;", os.path.getsize(f"{site}/data/events.json"), "bytes;", len(slims), "páginas")


if __name__ == "__main__":
    main()
