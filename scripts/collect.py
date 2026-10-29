#!/usr/bin/env python3
"""Coleta diária sem navegador: busca os eventos de Curitiba em cada site de origem.

Uso: python3 collect.py RAW_DIR

Grava em RAW_DIR os arquivos que o dedupe.py lê:
- raw_eventoon.json: [[dd/mm/aaaa, título, local, endereço, slug, imagem], ...]
- raw_turismo.json:  [[slug, título, datas, horário, local, ingresso, site, img&tipo=N, categoria], ...]
- raw_extras.json:   {"<código>": [[id, título, início, fim, horário, local, caminho_url, dica], ...]}
- sources.json:      {"<código>": quantidade ou "erro: ..."} para o resumo da coleta

Cada site é independente: se um falhar, os outros seguem e o erro fica em sources.json.
É a versão em Python dos scripts de navegador que a coleta usava no PC.
"""
import json, os, re, sys, time, traceback
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 (+https://agendaocuritiba.github.io/)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
NOW = datetime.now(timezone.utc) - timedelta(hours=3)  # America/Sao_Paulo, sem horário de verão
MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def get(url, **kw):
    for i in range(3):
        try:
            r = S.get(url, timeout=40, **kw)
            if r.status_code in (429, 502, 503, 504) and i < 2:
                time.sleep(5 * (i + 1)); continue
            r.raise_for_status()
            return r
        except requests.ConnectionError:
            if i == 2:
                raise
            time.sleep(5 * (i + 1))


def post(url, **kw):
    r = S.post(url, timeout=40, **kw)
    r.raise_for_status()
    return r


def soup(html):
    return BeautifulSoup(html, "html.parser")


def text(el):
    return el.get_text(strip=True) if el else ""


def leaves(el):
    """Textos dos elementos sem filhos (como children.length === 0 no navegador)."""
    return [t.get_text(strip=True) for t in el.find_all(True) if not t.find(True) and t.get_text(strip=True)]


def iso_dm(d, m):
    """Dia/mês sem ano: este ano, ou o próximo se o mês já passou."""
    y = NOW.year + (1 if m < NOW.month else 0)
    return f"{y}-{m:02d}-{d:02d}"


def local_iso(s):
    """Data/hora ISO com fuso → horário de Brasília, 'aaaa-mm-ddThh:mm'."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo:
        dt = dt.astimezone(timezone(timedelta(hours=-3)))
    return dt.strftime("%Y-%m-%dT%H:%M")


def ld_json(doc):
    out = []
    for x in doc.find_all("script", type="application/ld+json"):
        try:
            j = json.loads(x.string or x.get_text())
        except Exception:
            continue
        for item in (j if isinstance(j, list) else [j]):
            out.extend(item.get("@graph", [item]) if isinstance(item, dict) else [])
    return out


def is_type(j, rx):
    return re.search(rx, ",".join(j.get("@type", []) if isinstance(j.get("@type"), list) else [str(j.get("@type", ""))]))


# ---------------------------------------------------------------- sites

def eventoon():
    base = "https://www.eventoon.com.br/"
    page = soup(get(base + "cidade/curitiba-pr").text)
    base = (page.body or {}).get("data-baseurl") or base
    allx, pgs, p = {}, 1, 1
    while p <= pgs:
        r = post(base + "ListaEventos/getEventos", data={"offset": p, "artista": "", "cidade": "2878", "estado": "18"},
                 headers={"X-Requested-With": "XMLHttpRequest"}).json()
        pgs = int(r.get("qtd_pgs") or 1)
        for c in soup(r.get("html", "")).select("div.col-md-12.col-sm-12"):
            a = c.select_one('a[href*="/evento/"]')
            info = c.select_one(".col-md-5")
            if not a or not info:
                continue
            sp = [text(s) for s in info.select("div > span")]
            img = c.find("img")
            href = a["href"]
            allx[href] = [info.find("small").get_text() if info.find("small") else "", text(info.find("label")),
                          sp[0] if sp else "", sp[2] if len(sp) > 2 else "",
                          href.replace("https://www.eventoon.com.br/evento/", ""), img.get("src", "") if img else ""]
        p += 1
    return list(allx.values())


def turismo():
    base = "https://turismo.curitiba.pr.gov.br"
    hoje = NOW.strftime("%d-%m-%Y")
    links, p, mx = [], 1, 1
    while p <= mx:
        d = soup(get(f"{base}/eventos/{hoje}/{p}").text)
        links += [requests.compat.urljoin(base, a["href"]) for a in d.select('h4 a[href*="/evento/"]')]
        nums = [int(a["href"].rstrip("/").split("/")[-1]) for a in d.select(f'a[href*="/eventos/{hoje}/"]')
                if a["href"].rstrip("/").split("/")[-1].isdigit()]
        mx = max([mx] + nums)
        p += 1
    out = []
    for u in dict.fromkeys(links):
        d = soup(get(u).text)
        t = d.body.get_text("\n") if d.body else ""

        def g(k):
            m = re.search(k + r"\s*:\s*([^\n]+)", t)
            return m.group(1).strip() if m else ""

        img = next((i.get("src", "") for i in d.find_all("img") if "imagem.ashx" in i.get("src", "")), "")
        im = re.search(r"img=([^&]+&tipo=\d+)", img)
        title = (d.title.get_text() if d.title else "").replace(" - Turismo Curitiba", "").strip()
        out.append([u.replace(base + "/evento/", ""), title, g(r"Data\(s\)"), g("Horário"), g("Local"),
                    g("Ingresso"), g("Site"), im.group(1) if im else "", text(d.select_one(".categoria"))])
    return out


def disk():
    allx = []
    for f in range(0, 600, 100):
        r = post(f"https://www.diskingressos.com.br/home/_search?size=100&from={f}", data="{}",
                 headers={"Content-Type": "application/json"}).json()
        hits = r["hits"]["hits"]
        allx += [h["_source"] for h in hits]
        if len(hits) < 100:
            break
    out = []
    for s in allx:
        if not re.fullmatch(r"(?i)curitiba", (s.get("city") or "").strip()):
            continue
        grupo = bool(re.search(r"-G$", s["uid"]))
        oh = s.get("openhouse") or ""
        t = oh[11:16] if (not grupo and oh and not oh.startswith("01-01-0001")) else ""
        out.append([s["uid"], s["eventname"].strip(), s["date"], (s.get("endsale") or s["date"]) if grupo else s["date"], t,
                    s.get("local") or "", f"grupo/{s['groupid']}" if grupo else f"event/{s['id']}",
                    ", ".join(c.strip() for c in s.get("classification") or [])])
    return out


SYMPLA_SKIP = re.compile(r"\bcurso\b|workshop|\baulas?\b|forma[cç][aã]o|mentoria|treinamento|certifica|oficina|graduation|"
                         r"turma (adulto|infantil)|semin[aá]rio|sele[cç][aã]o de talentos", re.I)


def sympla():
    cats = {"show-musica-festa": "Show", "teatro-espetaculo": "Teatro", "stand-up-comedy": "Stand-up",
            "gastronomico": "Gastronomia", "infantil": "Infantil", "experiencias": ""}

    def pd(t):
        r = [iso_dm(int(d), MESES[m.lower()]) for d, m in re.findall(r"(\d{1,2}) de ([A-Za-zç]{3})", t) if m.lower() in MESES]
        h = re.search(r"às (\d{1,2}):(\d{2})", t)
        return (r[0] if r else ""), (r[1] if len(r) > 1 else (r[0] if r else "")), (f"{h.group(1)}:{h.group(2)}" if h else "")

    allx = {}
    for c, lab in cats.items():
        for p in range(1, 41):
            d = soup(get(f"https://www.sympla.com.br/eventos/curitiba-pr/{c}?page={p}").text)
            links = d.select('a[href*="/evento/"]')
            if not links:
                break
            for a in links:
                href = a["href"]
                m = re.search(r"/(\d+)(\?|$)", href)
                if not m or m.group(1) in allx:
                    continue
                loc = text(a.find("p"))
                lm = re.match(r"^(?:(.*) - )?([^,]+), PR$", loc)
                if not lm or not re.fullmatch(r"(?i)curitiba", lm.group(2).strip()):
                    continue
                dt = next((x for x in leaves(a) if re.search(r" de [A-Z]", x)), "")
                s, e, t = pd(dt)
                allx[m.group(1)] = [m.group(1), text(a.find("h3")), s, e, t, (lm.group(1) or "").strip(),
                                    href.split("?")[0].replace("https://www.sympla.com.br/evento/", ""), lab]
            time.sleep(0.3)
    return [x for x in allx.values() if x[2] and not SYMPLA_SKIP.search(x[1])]


def blueticket():
    a = get("https://api2-cdn.blueticket.com.br/events?city=Curitiba",
            headers={"Origin": "https://www.blueticket.com.br", "Referer": "https://www.blueticket.com.br/"}).json()
    return [[e["id"], e["name"].strip(), e["date"][:10], e["date"][:10], e["date"][11:16], e.get("venue") or "",
             f"{e['id']}/{e['slug']}", e.get("category") or ""] for e in a if e.get("cityName") == "Curitiba"]


def bilheteria():
    M = {"janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
         "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
    seen = {}
    for p in range(1, 21):
        d = soup(get(f"https://www.bilheteriadigital.com/PR/as/{p}").text)
        add = 0
        for a in d.find_all("a", href=True):
            if not a.find("img") or a["href"] in seen:
                continue
            add += 1
            seen[a["href"]] = leaves(a)
        if not add:
            break
    out = []
    for h, l in seen.items():
        if "Curitiba - PR" not in l:
            continue
        i = l.index("Curitiba - PR")
        m = re.match(r"(\d{1,2}) de (\S+)", next((t for t in l if re.match(r"\d{1,2} de ", t)), ""))
        if not m or m.group(2).lower() not in M:
            continue
        dt = iso_dm(int(m.group(1)), M[m.group(2).lower()])
        path = h.replace("https://www.bilheteriadigital.com", "").lstrip("/")
        out.append([path, l[0], dt, dt, "", l[i + 1] if i + 1 < len(l) else "", path, ""])
    return out


def ingresse():
    c = {}
    for o in range(0, 5000, 100):
        try:
            j = get(f"https://api-site.ingresse.com/events/search?company_id=1&size=100&order_by_date=true&offset={o}").json()
        except Exception:
            break
        if not j.get("events"):
            break
        for e in j["events"]:
            if re.search(r"(?i)curitiba", (e.get("place") or {}).get("city") or ""):
                l = local_iso((e.get("session") or {}).get("dateTime"))
                c[e["id"]] = [e["id"], e["title"].strip(), l[:10], l[:10], l[11:16], (e.get("place") or {}).get("name") or "",
                              e.get("slug") or "", ", ".join(x.get("name", "") if isinstance(x, dict) else str(x) for x in e.get("categories") or [])]
    return list(c.values())


def fever():
    base = "https://feverup.com"
    home = soup(get(base + "/pt/curitiba").text)
    il = next((j for j in ld_json(home) if j.get("@type") == "ItemList"), {})
    ids = set()

    def grab(d):
        for a in d.select('a[href*="/m/"]'):
            m = re.search(r"/m/(\d+)", a["href"])
            if m:
                ids.add(m.group(1))

    grab(home)
    for item in il.get("itemListElement", []):
        try:
            grab(soup(get(item["url"]).text))
        except Exception:
            pass
    out = []
    for i in sorted(ids):
        try:
            d = soup(get(f"{base}/m/{i}").text)
        except Exception:
            continue
        ev = next((j for j in ld_json(d) if j.get("@type") == "Event"), None)
        if not ev or not ev.get("startDate"):
            continue
        loc = ev.get("location")
        loc = loc[0] if isinstance(loc, list) else (loc or {})
        s, e = ev["startDate"][:10], (ev.get("endDate") or ev["startDate"])[:10]
        out.append([i, re.sub(r"\s*-\s*Curitiba$", "", ev["name"]), s, e,
                    ev["startDate"][11:16] if s == e and len(ev["startDate"]) > 10 else "", loc.get("name", ""), i,
                    "Concerto" if re.search(r"(?i)candlelight", ev["name"]) else ""])
        time.sleep(0.3)
    return out


def ingressocom():
    j = get("https://www.ingresso.com/api/events?event_type=&per_page=99999").json()
    return [[e["id"], e["title"], e["start_date"], e["end_date"], "", (e.get("place") or {}).get("name") or "", e["path"],
             (e.get("event_type") or {}).get("name") or ""]
            for e in j.get("events", []) if re.search(r"Curitiba/PR", (e.get("place") or {}).get("full_address") or "")
            and not re.search(r"(?i)cinema", (e.get("event_type") or {}).get("name") or "")]


def guaira():
    base = "https://www.teatroguaira.pr.gov.br"
    links = {}
    for p in range(0, 15):
        d = soup(get(f"{base}/calendario-eventos" + (f"?page={p}" if p else "")).text)
        novos = [a["href"].split("?")[0].split("#")[0] for a in d.find_all("a", href=True) if re.match(r"(/|https://www\.teatroguaira\.pr\.gov\.br/)Evento/", a["href"])]
        novos = [h for h in novos if h not in links]
        if not novos:
            break
        links.update(dict.fromkeys(novos))
    out = []
    for h in links:
        u = requests.compat.urljoin(base, h)
        path = u.replace(base + "/", "")
        d = soup(get(u).text)
        ev = next((j for j in ld_json(d) if is_type(j, "Event") and j.get("startDate")), None)
        if ev:
            a, b = local_iso(ev["startDate"]), local_iso(ev.get("endDate") or ev["startDate"])
            loc = ev.get("location") or {}
            loc = loc[0] if isinstance(loc, list) else loc
            hr = "" if a[11:16] == "00:00" else a[11:16]
            out.append([path, ev["name"].strip(), a[:10], max(a[:10], b[:10]), hr, loc.get("name") or "Teatro Guaíra", path, "Teatro"])
            continue
        tx = re.sub(r"\s+", " ", (d.find("main") or d.find("article") or d.body).get_text(" "))
        ds = sorted("-".join(reversed(x.split("/"))) for x in re.findall(r"\d{2}/\d{2}/\d{4}", tx))
        if not ds:
            continue
        og = d.find("meta", property="og:title")
        t = og["content"] if og and og.get("content") else (text(d.find("h1")) or text(d.title))
        t = re.sub(r"\s*[|–-]\s*Teatro Gua[ií]ra.*$", "", t, flags=re.I).strip()
        hr = re.search(r"(\d{1,2})h(\d{2})?", tx)
        sala = re.search(r"(Auditório [A-ZÁ-Úa-zá-ú ]+?|Guairinha|Guairão|Mini-?[Aa]uditório)(?=[ ,.\-])", tx)
        out.append([path, t, ds[0], ds[-1], hr.group(0) if hr else "",
                    f"Teatro Guaíra - {sala.group(1).strip()}" if sala else "Teatro Guaíra", path, "Teatro"])
    return out


EXTRAS = {"dk": disk, "sy": sympla, "bt": blueticket, "bd": bilheteria, "ig": ingresse, "fv": fever, "ic": ingressocom,
          "tg": guaira}


def main():
    raw = sys.argv[1]
    os.makedirs(raw, exist_ok=True)
    status, extras = {}, {}

    def run(code, fn):
        t0 = time.time()
        try:
            rows = fn()
            status[code] = len(rows)
        except Exception as e:
            traceback.print_exc()
            rows, status[code] = [], f"erro: {type(e).__name__}: {str(e)[:150]}"
        print(f"{code}: {status[code]} ({time.time() - t0:.0f} s)", flush=True)
        return rows

    json.dump(run("eo", eventoon), open(f"{raw}/raw_eventoon.json", "w"), ensure_ascii=False)
    json.dump(run("tc", turismo), open(f"{raw}/raw_turismo.json", "w"), ensure_ascii=False)
    for code, fn in EXTRAS.items():
        extras[code] = run(code, fn)
    json.dump(extras, open(f"{raw}/raw_extras.json", "w"), ensure_ascii=False)
    json.dump(status, open(f"{raw}/sources.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
