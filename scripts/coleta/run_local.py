"""Coleta sem Claude: abre cada site num Chromium (Playwright) e roda o .js correspondente.

Uso: python scripts/coleta/run_local.py OUT_DIR [--headless] [--only sy,tm]
Abre uma janela de navegador normal: o guia da Prefeitura recusa (403) o navegador sem janela.
Grava OUT_DIR/raw_eventoon.json, raw_turismo.json, raw_extras.json e coleta_log.json.
Os .js são rodados com semântica de REPL (await no topo, valor da última expressão),
igual à ferramenta de JavaScript do navegador do app.
"""
import argparse, json, os, sys, time, traceback
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SITES = [  # (chave, url, arquivo de saída ou None = extras)
    ("eventoon", "https://www.eventoon.com.br/cidade/curitiba-pr", "raw_eventoon.json"),
    ("guia", "https://guia.curitiba.pr.gov.br/evento/listar/", "raw_turismo.json"),
    ("dk", "https://www.diskingressos.com.br/", None),
    ("sy", "https://www.sympla.com.br/eventos/curitiba-pr", None),
    ("bt", "https://www.blueticket.com.br/", None),
    ("bd", "https://www.bilheteriadigital.com/", None),
    ("ig", "https://www.ingresse.com/", None),
    ("tm", "https://www.ticketmaster.com.br/", None),
    ("fv", "https://feverup.com/pt/curitiba", None),
    ("ic", "https://www.ingresso.com/eventos?city=curitiba", None),
    ("sg", "https://shotgun.live/pt-br/cities/curitiba", None),
    ("tg", "https://www.teatroguaira.pr.gov.br/calendario-eventos", None),
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")


def scroll_to_end(page, rounds=40):
    last = 0
    for _ in range(rounds):
        page.mouse.wheel(0, 20000)
        page.wait_for_timeout(800)
        h = page.evaluate("document.body.scrollHeight")
        if h == last:
            break
        last = h


def run_site(ctx, key, url):
    src = open(os.path.join(HERE, key + ".js"), encoding="utf-8").read()
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        if key == "sg":
            scroll_to_end(page)
        cdp = ctx.new_cdp_session(page)
        r = cdp.send("Runtime.evaluate", {"expression": src, "replMode": True,
                                          "awaitPromise": True, "returnByValue": True,
                                          "timeout": 600000})
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise RuntimeError((d.get("exception") or {}).get("description") or d.get("text"))
        val = r["result"].get("value")
        return json.loads(val) if isinstance(val, str) else val
    finally:
        page.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    only = set(filter(None, a.only.split(",")))
    extras, log = {}, {"started": datetime.now(timezone.utc).isoformat(), "sites": {}}
    with sync_playwright() as p:
        br = p.chromium.launch(headless=a.headless,
                               args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(user_agent=UA, locale="pt-BR", timezone_id="America/Sao_Paulo",
                             viewport={"width": 1366, "height": 900})
        for key, url, outfile in SITES:
            if only and key not in only:
                continue
            t0 = time.time()
            rows, err = None, None
            for tentativa in range(2):
                try:
                    rows = run_site(ctx, key, url)
                    if not isinstance(rows, list):
                        raise RuntimeError("resultado não é lista: %r" % (str(rows)[:200],))
                    err = None
                    break
                except Exception as e:
                    err = "%s: %s" % (type(e).__name__, str(e)[:500])
            n = len(rows) if rows is not None else 0
            log["sites"][key] = {"n": n, "secs": round(time.time() - t0), "error": err}
            print("%-9s %5d  %4ds  %s" % (key, n, time.time() - t0, err or ""), flush=True)
            if outfile:
                if rows is not None:
                    json.dump(rows, open(os.path.join(a.out, outfile), "w", encoding="utf-8"),
                              ensure_ascii=False)
            else:
                extras[key] = rows or []
        br.close()
    json.dump(extras, open(os.path.join(a.out, "raw_extras.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    log["finished"] = datetime.now(timezone.utc).isoformat()
    json.dump(log, open(os.path.join(a.out, "coleta_log.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    falhas = [k for k, v in log["sites"].items() if v["error"] or not v["n"]]
    print("falhas/vazios:", ", ".join(falhas) or "nenhum")


if __name__ == "__main__":
    main()
