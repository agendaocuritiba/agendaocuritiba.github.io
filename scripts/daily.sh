#!/usr/bin/env bash
# Coleta diária completa, só com scripts (roda no GitHub Actions, .github/workflows/coleta.yml).
# Coleta → deduplica → trava de tamanho → textos dos eventos novos → site → commit em main.
# Resumos e preços curtos dos eventos novos ficam em state/pending.json para a tarefa do Claude.
set -euo pipefail
cd "$(dirname "$0")/.."
HOJE=${HOJE:-$(TZ=America/Sao_Paulo date +%F)}
FIRST_RUN=2026-10-17

if [ "${FORCE:-}" != "1" ] && [ "$(python3 -c 'import json;print(json.load(open("state/runs.json"))[0]["run"])')" = "$HOJE" ]; then
  echo "Coleta de $HOJE já feita."; exit 0
fi

rm -rf work && mkdir -p work/raw work/out
python3 -u scripts/collect.py work/raw
python3 scripts/dedupe.py work/raw/raw_eventoon.json work/raw/raw_turismo.json work/raw/raw_extras.json \
  state/events.json "$HOJE" work/out work/raw/sources.json
if ! python3 scripts/guard.py work/out state/events.json "$HOJE"; then
  echo "::error::Trava de tamanho: coleta muito menor que a anterior. Nada foi publicado. Sites: $(cat work/raw/sources.json | tr -d '\n ')"
  exit 1
fi

# histórico: a coleta de hoje entra no início de state/runs.json, com o resultado de cada site
python3 - "$HOJE" <<'PY'
import json, sys
stats = json.load(open("work/out/stats.json"))
stats["sites"] = json.load(open("work/raw/sources.json"))
runs = [r for r in json.load(open("state/runs.json")) if r.get("run") != sys.argv[1]]
json.dump([stats] + runs[:179], open("state/runs.json", "w"), ensure_ascii=False, indent=1)
PY
cp work/out/events.json state/events.json

PYTHONPATH=scripts python3 -u scripts/details.py work/out state "$HOJE"

# resumos e preços de eventos que já passaram saem de state/
python3 - <<'PY'
import json
ids = {e["id"] for e in json.load(open("state/events.json"))}
for n in ("summaries", "prices"):
    p = f"state/{n}.json"
    d = json.load(open(p))
    json.dump({k: v for k, v in d.items() if k in ids}, open(p, "w"), ensure_ascii=False, indent=1)
PY

python3 scripts/build_site.py work/out "$HOJE" docs "$FIRST_RUN"

N=$(python3 -c 'import json;print(len(json.load(open("work/out/events.json"))))')
X=$(python3 -c "import json;print(sum(e['firstSeen']=='$HOJE' for e in json.load(open('work/out/events.json'))))")
if [ "$N" -lt 100 ]; then echo "::error::Só $N eventos; nada foi publicado."; exit 1; fi
echo "N=$N" >> "${GITHUB_OUTPUT:-/dev/null}"; echo "X=$X" >> "${GITHUB_OUTPUT:-/dev/null}"

if [ "${NO_PUSH:-}" = "1" ]; then echo "NO_PUSH: $N eventos, $X novos (sem commit)"; exit 0; fi
git add docs state
git -c user.name="Agendão Curitiba" -c user.email="agendaocuritiba@users.noreply.github.com" \
  commit -q -m "Coleta de $(TZ=America/Sao_Paulo date -d "$HOJE" +%d/%m/%Y): $N eventos, $X novos"
for i in 0 2 4 8 16; do sleep $i; git push origin HEAD:main && exit 0; git pull --rebase -q origin main || true; done
exit 1
