# Agendão Curitiba

Todos os eventos anunciados em Curitiba nos próximos seis meses, reunidos de dez sites.
Site: https://dennymarcels.github.io/agendao-curitiba/

- `docs/` é o site publicado no GitHub Pages (`index.html`, `data/events.json`, `e/<id>.html`, `sitemap.xml`).
- `scripts/dedupe.py` junta e deduplica a coleta; `scripts/build_site.py` gera os dados, as páginas de evento e o sitemap; `scripts/newsletter.py` monta a newsletter semanal.

Gerar o site: `python3 scripts/build_site.py OUT_DIR AAAA-MM-DD docs PRIMEIRA_COLETA`
(OUT_DIR com `events.json`, `stats.json` e `summaries.json`).

Erros ou pedidos de retirada: abra uma issue neste repositório.
