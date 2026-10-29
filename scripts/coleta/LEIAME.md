# Scripts de coleta no navegador

Cada arquivo `.js` desta pasta é rodado, inteiro, com a ferramenta de JavaScript do navegador do app, com a página indicada aberta. O resultado é uma string JSON: copie exatamente o que voltar. Se um site falhar, siga com os outros e anote qual falhou.

Evento ON e Turismo Curitiba vão cada um para o seu arquivo. Os outros devolvem linhas no formato [id, título, início aaaa-mm-dd, fim, horário, local, caminho_url, dica_categoria] e vão todos juntos para work/raw/raw_extras.json, como {"dk":[...],"sy":[...],"bt":[...],"bd":[...],"ig":[...],"tm":[...],"fv":[...],"ic":[...],"sg":[...],"tg":[...]}.

- `eventoon.js`: Evento ON → https://www.eventoon.com.br/cidade/curitiba-pr → salve em work/raw/raw_eventoon.json
- `turismo.js`: Turismo Curitiba → https://turismo.curitiba.pr.gov.br/eventos/ → salve em work/raw/raw_turismo.json (antes de rodar, troque DD-MM-AAAA no script pela data de hoje)
- `dk.js`: Disk Ingressos → https://www.diskingressos.com.br/
- `sy.js`: Sympla → https://www.sympla.com.br/eventos/curitiba-pr (demora ~30 s; se a ferramenta expirar, espere e leia window.__sy; os cartões às vezes mostram só "Curitiba, PR" sem o local, e o script aceita os dois formatos)
- `bt.js`: Blueticket → https://www.blueticket.com.br/
- `bd.js`: Bilheteria Digital → https://www.bilheteriadigital.com/
- `ig.js`: Ingresse → https://www.ingresse.com/
- `tm.js`: Ticketmaster → https://www.ticketmaster.com.br/ (demora; se expirar, espere e leia window.__tm)
- `fv.js`: Fever → https://feverup.com/pt/curitiba (itens sem data — cartões-presente, planos sem sessão — ficam de fora)
- `ic.js`: Ingresso.com → https://www.ingresso.com/eventos?city=curitiba (hoje costuma vir vazio; cinema não entra)
- `sg.js`: Shotgun → https://shotgun.live/pt-br/cities/curitiba (role a página até o fim antes de rodar, para carregar todos os cartões)
- `tg.js`: Teatro Guaíra → https://www.teatroguaira.pr.gov.br/calendario-eventos (site novo nesta rotina: se voltar vazio, olhe a página, ajuste o script na hora e descreva o ajuste na resposta final)

Se precisar ajustar um script durante a coleta (um site mudou), use o ajuste na hora e descreva-o na resposta final, para que ele seja levado para cá.
