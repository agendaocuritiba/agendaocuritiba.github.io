# Scripts de coleta no navegador

Cada arquivo `.js` desta pasta é rodado, inteiro, com a ferramenta de JavaScript do navegador do app, com a página indicada aberta. O resultado é uma string JSON: copie exatamente o que voltar. Se um site falhar, siga com os outros e anote qual falhou.

Evento ON e o guia da Prefeitura vão cada um para o seu arquivo. Os outros devolvem linhas no formato [id, título, início aaaa-mm-dd, fim, horário, local, caminho_url, dica_categoria] e vão todos juntos para work/raw/raw_extras.json, como {"dk":[...],"sy":[...],"bt":[...],"bd":[...],"ig":[...],"tm":[...],"fv":[...],"ic":[...],"sg":[...],"tg":[...]}.

- `eventoon.js`: Evento ON → https://www.eventoon.com.br/cidade/curitiba-pr → salve em work/raw/raw_eventoon.json
- `guia.js`: Guia da Prefeitura de Curitiba → https://guia.curitiba.pr.gov.br/evento/listar/ → salve em work/raw/raw_turismo.json (o arquivo mantém o nome da fonte antiga: a agenda do Turismo Curitiba, turismo.curitiba.pr.gov.br/eventos, saiu do ar em 11/2026 e foi para este guia). Lê a lista toda pela API do site (`/Evento/VerMais`) e abre a página de cada evento que entra; leva uns 30 s, e se a ferramenta expirar, rode de novo. Só entram eventos com data: cinema, cursos e oficinas, leilões, parques, esportes, saúde, museus, artesanato, atrações permanentes, programação contínua de meses e a rotina das Casas da Leitura (contação de histórias, rodas de leitura) ficam de fora.
- `dk.js`: Disk Ingressos → https://www.diskingressos.com.br/
- `sy.js`: Sympla → https://www.sympla.com.br/eventos/curitiba-pr (usa a API do próprio site, `/api/discovery-bff/search/category-type`, com as coleções 17 Festas e shows, 10 Arte/cinema/lazer, 1 Gastronomia e 12 Games/geek; costuma levar uns 10 s; se a ferramenta expirar, espere e leia window.__sy)
- `bt.js`: Blueticket → https://www.blueticket.com.br/
- `bd.js`: Bilheteria Digital → https://www.bilheteriadigital.com/
- `ig.js`: Ingresse → https://www.ingresse.com/
- `tm.js`: Ticketmaster → https://www.ticketmaster.com.br/ (demora; se expirar, espere e leia window.__tm)
- `fv.js`: Fever → https://feverup.com/pt/curitiba (itens sem data — cartões-presente, planos sem sessão — ficam de fora)
- `ic.js`: Ingresso.com → https://www.ingresso.com/eventos?city=curitiba (hoje costuma vir vazio; cinema não entra)
- `sg.js`: Shotgun → https://shotgun.live/pt-br/cities/curitiba (role a página até o fim antes de rodar, para carregar todos os cartões)
- `tg.js`: Teatro Guaíra → https://www.teatroguaira.pr.gov.br/calendario-eventos (site novo nesta rotina: se voltar vazio, olhe a página, ajuste o script na hora e descreva o ajuste na resposta final)

Se precisar ajustar um script durante a coleta (um site mudou), use o ajuste na hora e descreva-o na resposta final, para que ele seja levado para cá.
