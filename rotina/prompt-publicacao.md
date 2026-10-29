Publicação do site Agendão Curitiba (https://agendaocuritiba.github.io/). Responda em português. Esta tarefa roda à 0h (horário de Brasília). A coleta roda às 22h no PC do Denny e deixa os dados no dashboard https://claude.ai/artifact/VC7u1GsWLVdSCTyoz7KwxF; aqui você só leva esses dados para o site.

PASSO 1 — Datas: HOJE = `TZ=America/Sao_Paulo date +%F` e ONTEM = `TZ=America/Sao_Paulo date -d yesterday +%F`.

PASSO 2 — Repositório: use o repositório do site já clonado nesta sessão (agendaocuritiba/agendaocuritiba.github.io; o nome antigo dennymarcels/agendao-curitiba redireciona para ele). Dentro dele: `git fetch origin main && git checkout -B main origin/main`.

PASSO 3 — Há coleta nova? ArtifactData "get" (url do dashboard), collection "datasets", doc_id "events". Converta updated.at para America/Sao_Paulo; COLETA = essa data (AAAA-MM-DD). Se COLETA não for ONTEM nem HOJE, PARE: responda só "Ainda sem coleta nova no dashboard." e não mande aviso.

PASSO 4 — Já publicada? Leia `meta.updated` em docs/data/events.json. Se for igual a COLETA, PARE: responda só "Esta coleta já foi publicada." e não mande aviso.

PASSO 5 — Dados: anote source.url (/_blob/<id>) e baixe com Artifact action "read", url do dashboard, path "<id>", salvando como work/out/events.json (crie a pasta; work/ está no .gitignore). Leia com ArtifactData "get" os documentos site/summaries e site/prices; grave o campo items de cada um em work/out/summaries.json e work/out/prices.json e também em state/summaries.json e state/prices.json (JSON com ensure_ascii=False, indent=1). Se algum documento não existir, use {}.

PASSO 6 — Site: rode `python3 scripts/build_site.py work/out COLETA docs 2026-10-17` (use a data da coleta, não a de hoje: é ela que marca os eventos novos). Ele gera docs/data/events.json, as páginas docs/e/ e o sitemap. Se o número de eventos for menor que 100, PARE sem publicar e avise (algo deu errado na coleta).

PASSO 7 — Publicar: N = total de eventos, X = eventos com firstSeen == COLETA em work/out/events.json. `git add docs state`, commit com a mensagem "Coleta de DD/MM/AAAA (data COLETA): N eventos, X novos" e `git push origin HEAD:main` (se falhar por rede, tente de novo até 4 vezes, esperando 2, 4, 8 e 16 s). Nunca force o push.

PASSO 8 — Aviso: PushNotification (status "proactive") com "Agendão Curitiba publicado: N eventos, X novos — https://agendaocuritiba.github.io/". Se o push falhar, avise "Agendão Curitiba: a publicação falhou (<motivo>)" em vez disso.
