# Agendão Curitiba

Todos os eventos anunciados em Curitiba nos próximos seis meses, reunidos de dez sites.
Site: https://agendaocuritiba.github.io/

- `docs/` é o site publicado no GitHub Pages (`index.html`, `data/events.json`, `e/<id>.html`, `sitemap.xml`).
- `state/` guarda os resumos (`summaries.json`) e preços (`prices.json`) por id de evento, escritos pela coleta diária só para eventos novos, `pagos.json` ({id: motivo}), com os eventos que uma fonte marca como gratuitos por engano, e `sem_data.json` ({id: motivo}), com os eventos cuja data ainda não foi divulgada (ficam só no primeiro dia, com o selo "Data a definir"; o `dedupe.py` já marca sozinho os anúncios de vendedores que cobrem um mês inteiro, do dia 1 ao fim).
- `scripts/guard.py` impede a publicação quando a coleta vem muito menor que a anterior.
- `scripts/dedupe.py` junta e deduplica a coleta; `scripts/build_site.py` gera os dados, as páginas de evento e o sitemap; `scripts/newsletter.py` monta a newsletter semanal.

Gerar o site: `python3 scripts/build_site.py OUT_DIR AAAA-MM-DD docs PRIMEIRA_COLETA`
(OUT_DIR com `events.json`, `stats.json` e `summaries.json`).

Erros ou pedidos de retirada: abra uma issue neste repositório.
