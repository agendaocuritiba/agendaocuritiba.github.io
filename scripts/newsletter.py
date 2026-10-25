#!/usr/bin/env python3
"""Agenda Curitiba — monta a newsletter semanal a partir da saída do dedupe.py.

Uso:  python3 newsletter.py OUT_DIR RUN_DATE
Lê OUT_DIR/events.json e OUT_DIR/stats.json e grava:
  OUT_DIR/newsletter_subject.txt, OUT_DIR/newsletter.html, OUT_DIR/newsletter.txt
"""
import json, sys, html
from datetime import date, timedelta

DASH = "https://claude.ai/artifact/VC7u1GsWLVdSCTyoz7KwxF"
DOW = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
DOW_FULL = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MAX_NEW = 80


def br(d):
    return d.strftime("%d/%m")


def link(ev):
    return next((o["url"] for o in ev["originals"] if o.get("url")), DASH)


def on_day(ev, d):
    iso = d.isoformat()
    if ev.get("dates"):
        return iso in ev["dates"]
    return ev["start"] <= iso <= ev["end"]


def main():
    out, run = sys.argv[1], sys.argv[2]
    today = date.fromisoformat(run)
    week_end = today + timedelta(days=7)
    events = json.load(open(f"{out}/events.json"))
    stats = json.load(open(f"{out}/stats.json"))
    n_sites = len([k for k, v in stats["bySource"].items() if v])
    horizon = date.fromisoformat(stats["horizon"])
    new = sorted([e for e in events if e.get("firstSeen") == run], key=lambda e: e["start"])

    subject = f"Agenda Curitiba — próximos 7 dias ({today.strftime('%d')} a {br(week_end)})"
    esc = html.escape
    H, T = [], []

    def row(ev, show_date):
        d = date.fromisoformat(ev["start"])
        when = f"{DOW[d.weekday()]} {br(d)}" if show_date else ""
        if show_date and ev["end"] != ev["start"]:
            when += f" a {br(date.fromisoformat(ev['end']))}"
        meta = " · ".join(x for x in [when, ev.get("time", ""), ev.get("venue", ""), ", ".join(ev["sources"])] if x)
        H.append(f'<li><a href="{esc(link(ev))}">{esc(ev["title"])}</a> <i>{esc(ev["category"])}</i><br><small>{esc(meta)}</small></li>')
        T.append(f"- {ev['title']} [{ev['category']}] — {meta} — {link(ev)}")

    H.append('<style>ul{list-style:none;padding:0;margin:0}li{padding:5px 0;border-bottom:1px solid #eee}li a{color:#1a4fa0;font-weight:bold;text-decoration:none}'
             'i{font-style:normal;font-size:11px;color:#fff;background:#888;border-radius:3px;padding:1px 5px}small{color:#555}'
             'h2{font-size:19px;border-bottom:2px solid #1a4fa0;padding-bottom:4px;margin-top:26px}h3{font-size:15px;margin:14px 0 2px;color:#1a4fa0}</style>'
             '<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;color:#222">')
    H.append('<h1 style="margin:0 0 4px;font-size:24px">Agenda Curitiba</h1>')
    H.append(f'<p style="margin:0 0 12px;color:#666">{stats["events"]} eventos até {horizon.strftime("%d/%m/%Y")} · '
             f'coleta de {today.strftime("%d/%m/%Y")} · {n_sites} sites · {stats["new"]} novos</p>')
    H.append(f'<p><a href="{DASH}" style="display:inline-block;background:#1a4fa0;color:#fff;padding:10px 18px;'
             f'border-radius:6px;text-decoration:none;font-weight:600">Abrir o dashboard completo</a></p>')
    H.append(f'<p style="font-size:12px;color:#888">Se o botão não aparecer: {DASH}</p>')
    T += ["Agenda Curitiba",
          f"{stats['events']} eventos até {horizon.strftime('%d/%m/%Y')} · coleta de {today.strftime('%d/%m/%Y')} · {n_sites} sites · {stats['new']} novos",
          f"Dashboard: {DASH}", ""]

    # Próximos 7 dias, agrupados por dia
    week = [e for e in events if e["start"] <= week_end.isoformat() and e["end"] >= run]
    H.append(f'<h2>Próximos 7 dias ({len(week)})</h2>')
    T.append(f"PRÓXIMOS 7 DIAS ({len(week)})")
    multi = [e for e in week if e["end"] != e["start"]]
    single = [e for e in week if e["end"] == e["start"]]
    d = today
    while d <= week_end:
        day = sorted([e for e in single if on_day(e, d)],
                     key=lambda e: (e["end"] != e["start"], e.get("time") or "99", e["title"]))
        if day:
            H.append(f'<h3>{DOW_FULL[d.weekday()]}, {br(d)} ({len(day)})</h3><ul>')
            T.append(f"\n{DOW_FULL[d.weekday()]}, {br(d)}")
            for ev in day:
                row(ev, False)
            H.append("</ul>")
        d += timedelta(days=1)

    if multi:
        H.append(f'<h3>Temporadas e eventos de vários dias ({len(multi)})</h3><ul>')
        T.append("\nTemporadas e eventos de vários dias")
        for ev in sorted(multi, key=lambda e: e["title"]):
            row(ev, True)
        H.append("</ul>")

    # Novos nesta coleta
    H.append(f'<h2>Novos nesta coleta ({len(new)})</h2>')
    T.append(f"\nNOVOS NESTA COLETA ({len(new)})")
    if new:
        H.append('<ul>')
        for ev in new[:MAX_NEW]:
            row(ev, True)
        H.append("</ul>")
        if len(new) > MAX_NEW:
            H.append(f'<p style="color:#666">…e mais {len(new) - MAX_NEW} no dashboard.</p>')
    else:
        H.append('<p style="color:#666">Nenhum evento novo desde a coleta anterior.</p>')

    H.append('<p style="font-size:11px;color:#999;margin-top:28px">Enviado automaticamente pela coleta semanal da Agenda Curitiba.</p></div>')

    open(f"{out}/newsletter_subject.txt", "w").write(subject)
    open(f"{out}/newsletter.html", "w").write("".join(H))
    open(f"{out}/newsletter.txt", "w").write("\n".join(T))
    print(subject, "|", len(week), "eventos na semana |", len(new), "novos |", len("".join(H)), "bytes de HTML")


if __name__ == "__main__":
    main()
