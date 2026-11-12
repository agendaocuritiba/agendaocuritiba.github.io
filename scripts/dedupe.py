#!/usr/bin/env python3
"""Agenda Curitiba — agrega eventos de vários sites, deduplica e compara com o cache.

Uso:
  python3 dedupe.py RAW_EVENTOON RAW_TURISMO RAW_EXTRAS PREV_EVENTS RUN_DATE OUT_DIR

- RAW_EVENTOON: [[dd/mm/aaaa, título, local, endereço, slug, imagem], ...]
- RAW_TURISMO:  [[slug/id, título, "dd/mm/aaaa[ a dd/mm/aaaa]", horário, local,
                  ingresso, site, "img&tipo=N", categoria], ...]
- RAW_EXTRAS:   {"<código>": [[id, título, início aaaa-mm-dd, fim, horário, local,
                  caminho_url, dica_categoria], ...], ...}  — códigos em SOURCES abaixo
- PREV_EVENTS:  lista de eventos da coleta anterior (ou [])
- RUN_DATE:     data da coleta (aaaa-mm-dd)
Gera OUT_DIR/events.json e OUT_DIR/stats.json.
"""
import json, re, sys, hashlib, unicodedata
from datetime import date, timedelta

EO_BASE = "https://www.eventoon.com.br/evento/"
TC_BASE = "https://turismo.curitiba.pr.gov.br/evento/"
TC_IMG = "https://turismo.curitiba.pr.gov.br/include/handler/imagem.ashx?img={}&x=600&y=400"

# código → (nome exibido, prefixo da URL)
SOURCES = {
    "dk": ("Disk Ingressos", "https://www.diskingressos.com.br/"),
    "fv": ("Fever", "https://feverup.com/m/"),
    "sy": ("Sympla", "https://www.sympla.com.br/evento/"),
    "bt": ("Blueticket", "https://www.blueticket.com.br/evento/"),
    "bd": ("Bilheteria Digital", "https://www.bilheteriadigital.com/"),
    "ig": ("Ingresse", "https://www.ingresse.com/"),
    "tm": ("Ticketmaster", "https://www.ticketmaster.com.br/event/"),
    "ic": ("Ingresso.com", "https://www.ingresso.com/evento/"),
    "sg": ("Shotgun", "https://shotgun.live/pt-br/events/"),
    "tg": ("Teatro Guaíra", "https://www.teatroguaira.pr.gov.br/"),
}
SOURCE_ORDER = ["Turismo Curitiba", "Evento ON", "Disk Ingressos", "Sympla", "Blueticket",
                "Bilheteria Digital", "Ticketmaster", "Ingresse", "Fever", "Ingresso.com", "Shotgun", "Teatro Guaíra"]

STOP = set("""a o as os e de da do das dos em no na nos nas com para por ao the and of in
curitiba cwb pr brasil show shows turne tour live ao vivo esgotado sessao extra edicao
apresenta apr club vibe 2026 2027 data venda geral banco stand up comedy
segunda terca quarta quinta sexta sabado domingo 2x1""".split())
ALIAS = {"jr": "junior"}
VENUE_STOP = set("a o as os e de da do das dos em no na com the curitiba cwb pr teatro bar casa espaco centro cultural auditorio sala clube club hall local definir".split())


def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tokens(title, stop=STOP):
    t = strip_acc(title.lower()).replace("'", "").replace("’", "")
    out = set()
    for w in re.findall(r"[a-z0-9]+", t):
        w = ALIAS.get(w, w)
        if w in stop or (len(w) < 2 and not w.isdigit()) or (w.isdigit() and len(w) <= 2):
            continue
        if stop is STOP and re.fullmatch(r"\d{1,2}h\d{0,2}", w):  # horário da sessão ("20h00")
            continue
        out.add(w)
    return out


# Título que é só a sessão ("Sábado| 16h - 18h ou 20h30", "Estreia sexta 20h30"): alguns produtores
# na Sympla criam uma página por dia e põem o horário no lugar do nome do espetáculo.
SCHEDULE_WORDS = set("""segunda terca quarta quinta sexta sabado domingo feira seg ter qua qui sex sab dom
estreia sessao sessoes horario horarios dia dias hoje amanha noite tarde manha matine fim semana
feriado extra ou e a as o os de do da das dos ao partir em
janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro
jan fev mar abr mai jun jul ago set out nov dez""".split())


def schedule_only(t):
    words = re.findall(r"[a-z0-9]+", strip_acc(t.lower()))
    return bool(words) and all(w in SCHEDULE_WORDS or re.fullmatch(r"\d{1,4}(h\d{0,2})?", w) for w in words)


def pdate(s):
    d, m, y = s.strip().split("/")
    return date(int(y), int(m), int(d))


def clean_title(t):
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+em Curitiba\b.*?(?=$| - | \|)", "", t, flags=re.I).strip(" -|,")
    t = re.sub(r"^Esgotado\s*-\s*", "", t, flags=re.I)
    t = re.sub(r"\s*\[club vibe\]\s*", " ", t, flags=re.I).strip()
    t = t.replace("“", "").replace("”", "").strip()
    if " - " in t:
        head, tail = t.rsplit(" - ", 1)
        if tokens(tail) and tokens(tail) <= tokens(head):
            t = head.strip()
    if t.isupper() and len(t) > 6:
        t = t.title()
    return t


def norm_time(s):
    s = (s or "").strip().rstrip(".")
    m = re.match(r"^(\d{1,2})[:h](\d{2})$", s)
    if m:
        return f"{int(m.group(1))}h" + ("" if m.group(2) == "00" else m.group(2))
    return s


# Vendedores de ingresso anunciam uma sessão por página: fim no dia seguinte a uma sessão que
# começa à tarde ou à noite é a madrugada da mesma festa, não um segundo dia de evento.
SINGLE_SESSION = {"Sympla", "Shotgun", "Ticketmaster", "Fever", "Blueticket", "Ingresse", "Ingresso.com"}


def overnight(o, st, en):
    if o["source"] not in SINGLE_SESSION or en - st != timedelta(days=1):
        return False
    m = re.match(r"(\d{1,2})h", o["time"])
    # o Ticketmaster nem sempre mostra o horário, mas a página é sempre de um show só
    return int(m.group(1)) >= 17 if m else o["source"] == "Ticketmaster"


# Sem data definida: vendedores que ainda não marcaram o dia anunciam o mês inteiro (do dia 1 ao
# último dia; a Sympla manda o fim à meia-noite, que no horário de Brasília cai na véspera).
# O evento fica só no dia 1 (ou hoje, se o mês já começou) e ganha o selo "Data a definir".
VAGUE_SOURCES = SINGLE_SESSION | {"Disk Ingressos", "Bilheteria Digital"}


def month_only(o, st, en):
    if o["source"] not in VAGUE_SOURCES or st.day != 1:
        return False
    nxt = date(st.year + st.month // 12, st.month % 12 + 1, 1)
    return nxt - timedelta(days=2) <= en <= nxt


def load_originals(eo_raw, tc_raw, extras, today, horizon):
    origs = []

    def add(o):
        st, en = date.fromisoformat(o["start"]), date.fromisoformat(o["end"])
        o["time"] = norm_time(o.get("time"))
        if overnight(o, st, en):
            en = st; o["end"] = o["start"]
        if en < st:  # fim antes do início (erro do site, ex.: "12/12/2026 a 12/11/2026"): vale só o início
            en = st; o["end"] = o["start"]
        if en < today or st > horizon:
            return
        if st < today:
            o["start"] = today.isoformat()
        if month_only(o, st, en):
            # "until" guarda o mês anunciado, para juntar com as outras fontes do mesmo evento
            o["tbd"], o["until"], o["end"] = st.isoformat()[:7], o["end"], o["start"]
        origs.append(o)

    for d, t, v, a, slug, img in eo_raw:
        dt = pdate(d).isoformat()
        add({"oid": "eo:" + slug, "source": "Evento ON", "title": t.strip(), "url": EO_BASE + slug,
             "start": dt, "end": dt, "time": "", "venue": v.strip(), "address": a.strip(),
             "image": img, "category": "", "price": ""})
    for slug, t, ds, hr, loc, ing, site, img, cat in tc_raw:
        parts = [p.strip() for p in ds.split(" a ")]
        try:
            st = pdate(parts[0]); en = pdate(parts[-1])
        except Exception:
            continue
        venue, addr = (loc.split("|", 1) + [""])[:2] if "|" in loc else (loc, "")
        add({"oid": "tc:" + slug.split("/")[-1], "source": "Turismo Curitiba", "title": t.strip(),
             "url": TC_BASE + slug, "start": st.isoformat(), "end": en.isoformat(),
             "time": hr.strip(), "venue": venue.strip().rstrip("."), "address": addr.strip().rstrip("."),
             "image": TC_IMG.format(img) if img else "", "category": cat, "price": ing.strip().rstrip("."),
             "site": site.strip()})
    for code, rows in (extras or {}).items():
        if code not in SOURCES:
            continue
        name, base = SOURCES[code]
        for r in rows:
            rid, t, st, en, hr, venue, path, hint = (list(r) + [""] * 8)[:8]
            if not st:
                continue
            add({"oid": f"{code}:{rid}", "source": name, "title": str(t).strip(), "url": base + str(path),
                 "start": st, "end": en or st, "time": hr, "venue": str(venue).strip(), "address": "",
                 "image": "", "category": hint or "", "price": ""})
    return origs


def span(g):
    return (min(date.fromisoformat(o["start"]) for o in g), max(date.fromisoformat(o.get("until") or o["end"]) for o in g))


def overlap(a, b, tol=0):
    (as_, ae), (bs, be) = span(a), span(b)
    return as_ - timedelta(days=tol) <= be and bs - timedelta(days=tol) <= ae


def title_score(ta, tb):
    a, b = tokens(ta), tokens(tb)
    if not a or not b:
        return 0
    short = a if len(a) <= len(b) else b
    shared = a & b
    if len(short) == 1:
        w = next(iter(short))
        return 1.0 if (shared and len(w) >= 4) else (0.7 if shared else 0)
    if len(shared) < 2:
        return 0
    return len(shared) / len(short)


def venue_overlap(g1, g2):
    v1 = set().union(*(tokens(o["venue"], VENUE_STOP) for o in g1))
    v2 = set().union(*(tokens(o["venue"], VENUE_STOP) for o in g2))
    return bool(v1 & v2)


def group_score(g1, g2):
    best = 0
    for x in g1:
        for y in g2:
            if schedule_only(x["title"]) or schedule_only(y["title"]):
                continue  # sem nome não dá para comparar título
            best = max(best, title_score(clean_title(x["title"]), clean_title(y["title"])))
    if best == 0.7 and not venue_overlap(g1, g2):  # título de uma palavra curta: exige mesmo local
        return 0
    # título muito mais longo que o outro (ex.: "After não oficial Solomun") só junta se o local bater
    la = max(len(tokens(clean_title(o["title"]))) for o in g1)
    lb = max(len(tokens(clean_title(o["title"]))) for o in g2)
    sa = min(len(tokens(clean_title(o["title"]))) for o in g1)
    sb = min(len(tokens(clean_title(o["title"]))) for o in g2)
    if abs(max(la, lb) - min(sa, sb)) >= 4 and not venue_overlap(g1, g2):
        return 0
    return best


def cluster(origs):
    # 1) mesma fonte: mesmo título + mesmo local = sessões do mesmo evento
    bykey = {}
    for o in sorted(origs, key=lambda x: x["start"]):
        # títulos que são só a sessão: na mesma fonte e no mesmo local, são o mesmo espetáculo
        tk = "~sessao" if schedule_only(o["title"]) else " ".join(sorted(tokens(clean_title(o["title"]))))
        k = (o["source"], tk,
             " ".join(sorted(tokens(o["venue"], VENUE_STOP)))[:60])
        bykey.setdefault(k, []).append(o)
    groups = []
    for g in bykey.values():  # variações de título na mesma fonte (ex.: "Sessão extra", "| Banco do Brasil")
        for h in groups:
            if h[0]["source"] != g[0]["source"]:
                continue
            sc = group_score(g, h)
            # mesmo local: título bem parecido, ou parecido + mesmas datas (sessões do mesmo espetáculo);
            # sem local em comum: só título praticamente igual na mesma data
            if (venue_overlap(g, h) and (sc >= 0.8 or (sc >= 0.7 and overlap(g, h)))) or (sc >= 0.99 and overlap(g, h)):
                h.extend(g)
                break
        else:
            groups.append(list(g))
    # 2) entre fontes: título parecido + datas que se cruzam; nunca junta dois grupos da mesma fonte
    groups.sort(key=lambda g: SOURCE_ORDER.index(g[0]["source"]) if g[0]["source"] in SOURCE_ORDER else 99)
    merged = []
    for g in groups:
        srcs = {o["source"] for o in g}
        best, bs = None, 0
        for m in merged:
            if srcs & {o["source"] for o in m}:
                continue
            s = group_score(g, m)
            tol = 1 if s >= 0.99 else 0
            if s >= 0.6 and overlap(g, m, tol) and s > bs:
                best, bs = m, s
        if best is not None:
            best.extend(g)
        else:
            merged.append(list(g))
    return merged


# Classificação própria: o Turismo Curitiba usa "Lazer"/"Geral" para quase tudo.
KEEP_TC = {"Feira/Exposição", "Gastronomia", "Congresso"}
RULES = [
    ("Congresso", r"congresso|summit|simposio|seminario|conferencia|pitch day"),
    ("Gastronomia", r"gastronom|curitipao|assado|assafest|twelve beers|food|cerveja|beer|feijoad|costelad|jantar|almoco|vinho|\bwine\b(?! down)|chef pour|mao na massa|na taca|pintura em tacas|festa das nacoes|\bcafes? (especia|combina)|cafe e chocolate|sirene brazil"),
    ("Feira/Exposição", r"\bfeira\b|\bexpo|exposi|old & low car|old low car|esoteric|dinos alive|invasao alien|charm show|natal vegan|mostra de audiovisual"),
    ("Esporte", r"hardest run|corrida(?!s? das blogueiras)|maratona|futebol|campeonato|caminhada|aulao"),
    ("Stand-up", r"stand ?up|comedy|xaveca|piada|enterrado vivo|como nossos pais|afonso padilha|renato albani|ivangelica|indio behn|embrulha pra viagem|nada e combinado|leo lins|humor|improviso|bruna louise|diogo almeida|carol delgado|santo fole|danilo gentili|mallandro|silvetty montilla|victor sarro|jonathan nemer|conte uma fofoca"),
    ("Palestra", r"palestra|claudio duarte|padre patrick|catia damasceno|andrea vermont|paua em seja livre|encontro de valor|adultecer|fazimentos texteis"),
    ("Infantil", r"infantil|tum pa\b|aventura congelante|bicho-?papao|conto de fadas|poke fan fest|kids|crianca|bob esponja|megabolhas|vini pirata|tum tu tubos|parque mikewood|frozen|tres porquinhos|caca aos doces|halloween encantado|spidey|gabby|clubinho|toy story|biscoitos natalinos|papai noel dos correios"),
    ("Concerto", r"concerto|orquestra|symphon|sinfoni|in concert|\bcoral\b|\btrio\b|ensemble|classicos do cinema|zelda|zimmer|turandot|candlelight|catedral de luz|palacio avenida"),
    ("Teatro", r"musical|espetaculo|\bpeca\b|teatro(?! paiol)|danca(?! de salao)|gota d.agua|arqueologias do futuro|azaleia oriental|ballet|circo|nono paciente|improvavel|tarsila|misterio buffo|matilda|clube dos canalhas|antes que termine|no me kahlo|plantonistas|despertar da fenix|christmas dream|sonho de natal|disney|misterios s/?a|grande banquete|mostra|terapia infernal|baixa sociedade|kafka|madrugueiro|cidade de jornais|historieta|bela e a fera|morte e vida|capitulo xv|dois de nos|vendedor de sonhos|flamenca|zumbi e dandara|mia cara|manual para recem falecidos|desencantados|magico de oz|entre coroas e viloes|\bo santo\b|que ano foi este|fragmentos do infinito|festival homero|misterio do cristal|reino das aguas claras|onde mora o essencial|bug do multiverso|fabrica de emocoes|abrace o mundo|digestao emocio"),
    ("Festa/Balada", r"\bdj\b|all night|techno|after hours|solomun|vintage culture|\balok\b|\bbaile\b|garota sunset|five am|who we are|tranquilo apresenta|chemical surf|curitiba folia|moustache sound|bpm|\bclub vibe\b|\+55 bar|\bczar\b|ceu curitiba|eli iwasa|james zabiela|breaking beattz|showcase|\bgabe\b|\bliu\b|\bzac\b|\bvermont\b|halloween|hallowzot|festa|reveillon|virada|party|revoada|circus|escangalha|antiquario|carnaval|micareta|rumberos|k-pop|watch party|formatura|pink diamond|sabadao latino|ressaca pos show"),
    ("Festival", r"festival|fest\b|kemet"),
]
# shows de palco vendidos em sites de balada (ex.: Shotgun): o título manda, antes da dica do site
SHOW_RULES = [("Show", r"ze ibarra|sob ruido|ana paula da silva")]
HINT_RULES = [("Festa/Balada", r"balada|eletr[oô]nica"), ("Stand-up", r"stand ?up|com[eé]dia")]


def classify(g):
    tc_cat = next((o["category"] for o in g if o["source"] == "Turismo Curitiba" and o.get("category")), "")
    if tc_cat in KEEP_TC:
        return tc_cat
    text = strip_acc(" ".join(o["title"] for o in g).lower())
    venues = strip_acc(" ".join(o["venue"] for o in g).lower())
    hints = strip_acc(" ".join(o["category"] for o in g if o["source"] != "Turismo Curitiba").lower())
    for cat, rx in RULES[:5]:  # congresso, gastronomia, feira, esporte, stand-up: o título manda
        if re.search(rx, text):
            return cat
    for cat, rx in SHOW_RULES:
        if re.search(rx, text):
            return cat
    for cat, rx in HINT_RULES:
        if re.search(rx, hints):
            return cat
    for cat, rx in RULES[5:]:
        # o local só conta para festas (casas noturnas) e para o Teatro Barracão EnCena (só peças);
        # "Teatro Positivo" não faz de um show uma peça
        if re.search(rx, text) or (cat == "Festa/Balada" and re.search(rx, venues)) or (cat == "Teatro" and "barracao encena" in venues):
            return cat
    return "Show"


def build_event(g):
    g = sorted(g, key=lambda o: (SOURCE_ORDER.index(o["source"]) if o["source"] in SOURCE_ORDER else 99, o["start"]))
    tc = [o for o in g if o["source"] == "Turismo Curitiba"]
    named = [o for o in g if not schedule_only(o["title"])]
    tc = [o for o in tc if o in named]
    title = tc[0]["title"] if tc else min((clean_title(o["title"]) for o in named or g), key=len)
    if title.isupper() and len(title) > 6:
        title = title.title()
    # Fonte com só o mês: se outra fonte traz um dia de verdade (que não seja o dia 1 do mesmo
    # mês, data padrão de quem também não sabe), valem as outras; senão o evento fica sem data definida.
    vague = [o for o in g if o.get("tbd")]
    firsts = {o["start"] for o in vague}
    real = [o for o in g if not o.get("tbd") and not (o["start"] == o["end"] and o["start"] in firsts)]
    tbd = vague[0]["tbd"] if vague and not real else ""
    dated = g if tbd or not vague else [o for o in g if not o.get("tbd")]
    dates = set()
    for o in dated:
        d = date.fromisoformat(o["start"]); e = date.fromisoformat(o["end"])
        while d <= e and len(dates) <= 120:
            dates.add(d.isoformat()); d += timedelta(days=1)
    first = lambda f: next((o[f] for o in g if o.get(f)), "")
    venue = next((o["venue"] for o in g if len(o.get("venue", "")) >= 4 and not re.match(r"(?i)local a definir|curitiba$", o["venue"])), first("venue"))
    ev = {
        "title": title, "category": classify(g),
        "start": min(o["start"] for o in dated), "end": max(o["end"] for o in dated),
        "dates": sorted(dates) if len(dates) <= 60 else [],
        "time": next((o["time"] for o in g if o.get("time") and re.search(r"\d", o["time"])), first("time")),
        "venue": venue, "address": first("address"), "image": first("image"), "price": first("price"),
        "sources": sorted({o["source"] for o in g}, key=lambda s: SOURCE_ORDER.index(s) if s in SOURCE_ORDER else 99),
        "originals": g,
    }
    if not named:
        ev["badTitle"] = True  # título é só dia/horário: a coleta troca pelo nome real (PASSO 5)
    if tbd:
        ev["tbd"] = tbd  # "aaaa-mm": mês anunciado, dia ainda não definido
    return ev


def main():
    eo_p, tc_p, ex_p, prev_p, run, out = sys.argv[1:7]
    today = date.fromisoformat(run)
    m = today.month + 6; y = today.year + (m - 1) // 12; m = (m - 1) % 12 + 1
    horizon = date(y, m, min(today.day, 28 if m == 2 else 30 if m in (4, 6, 9, 11) else 31))
    load = lambda p, d: json.load(open(p)) if p and p != "-" else d
    origs = load_originals(load(eo_p, []), load(tc_p, []), load(ex_p, {}), today, horizon)
    prev = load(prev_p, [])
    prev_by_oid = {o["oid"]: p for p in prev for o in p.get("originals", [])}
    prev_orig = {o["oid"]: o for p in prev for o in p.get("originals", [])}

    events, used = [], set()
    for g in cluster(origs):
        ev = build_event(g)
        match = next((prev_by_oid[o["oid"]] for o in g if o["oid"] in prev_by_oid and prev_by_oid[o["oid"]]["id"] not in used), None)
        if match:
            ev["id"], ev["firstSeen"] = match["id"], match["firstSeen"]
            if ev.get("badTitle") and not schedule_only(match["title"]):
                ev["title"] = match["title"]  # nome real escrito numa coleta anterior
                del ev["badTitle"]
        else:
            ev["id"] = "e" + hashlib.sha1("|".join(sorted(o["oid"] for o in g)).encode()).hexdigest()[:12]
            ev["firstSeen"] = run
        used.add(ev["id"])
        for o in ev["originals"]:
            o["firstSeen"] = prev_orig.get(o["oid"], {}).get("firstSeen", run) if prev else run
        ev["updated"] = run
        events.append(ev)

    events.sort(key=lambda e: e["start"])
    ids = {e["id"] for e in events}
    by_src = {}
    for o in origs:
        by_src[o["source"]] = by_src.get(o["source"], 0) + 1
    stats = {
        "run": run, "horizon": horizon.isoformat(), "events": len(events), "originals": len(origs),
        "merged": sum(1 for e in events if len(e["sources"]) > 1),
        "new": sum(1 for e in events if e["firstSeen"] == run) if prev else 0,
        "removed": sum(1 for p in prev if p["id"] not in ids), "bySource": by_src,
        "eventoon": by_src.get("Evento ON", 0), "turismo": by_src.get("Turismo Curitiba", 0),
    }
    json.dump(events, open(f"{out}/events.json", "w"), ensure_ascii=False, indent=1)
    json.dump(stats, open(f"{out}/stats.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
