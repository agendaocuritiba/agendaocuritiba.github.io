const P=s=>new DOMParser().parseFromString(s,'text/html');
// Guia da Prefeitura de Curitiba (sucessor da agenda do Turismo Curitiba). Só entram eventos com data:
// ficam de fora cinema, cursos/oficinas, leilões, parques, esportes, saúde, museus (oficinas e visitas),
// artesanato e a programação de rotina das Casas da Leitura (Literatura entra só com lançamento, sarau etc.).
const SKIP=/^(Cinema|Cursos e workshops|Leilões|Parques|Esportes|Saúde e bem-estar|Museus|Artesanato)$/;
const LIT=/lançamento|sarau|feira|bate-papo|encontro com|exposição/i,ROTINA=/contação|roda de leitura|clubinho|clube de leitura/i;
const MES={jan:1,fev:2,mar:3,abr:4,mai:5,jun:6,jul:7,ago:8,set:9,out:10,nov:11,dez:12};
const cards=[];let p=0,total=1;
while(cards.length<total&&p<100){const body=new URLSearchParams({'filtro[Pagina]':p,'filtro[VerMais]':'true','filtro[Permanente]':'false','filtro[Orientacao]':'1'});const d=P(await fetch('/Evento/VerMais',{method:'POST',body}).then(r=>r.text()));total=+d.querySelector('#hidTotal')?.value||0;const cs=[...d.querySelectorAll('.evento-card')];if(!cs.length)break;cs.forEach(c=>{const a=c.querySelector('.evento-titulo a');cards.push({u:a.getAttribute('href'),t:a.textContent.trim(),cat:c.querySelector('.badge')?.textContent.trim()||'',dt:/\d/.test(c.querySelector('.bx-calendar-alt')?.parentElement.textContent||'')})});p++;}
const want=[...new Map(cards.map(c=>[c.u,c]))].map(x=>x[1]).filter(c=>c.dt&&!SKIP.test(c.cat)&&(c.cat!=='Literatura'||LIT.test(c.t)&&!ROTINA.test(c.t)));
const pd=s=>{const m=(s||'').match(/(\d{1,2}) de (\w{3})\w* de (\d{4})(?:, às (\d{1,2}:\d{2}))?/i);return m?{d:`${m[1].padStart(2,'0')}/${String(MES[m[2].toLowerCase()]).padStart(2,'0')}/${m[3]}`,iso:new Date(+m[3],MES[m[2].toLowerCase()]-1,+m[1]),h:m[4]||''}:null};
const out=[];
for(const c of want){try{const d=P(await fetch(c.u).then(r=>r.text()));const t=(d.querySelector('main')||d.body).textContent.replace(/[ \t]+/g,' ').replace(/\s*\n\s*/g,'\n');const g=k=>{const m=t.match(new RegExp(k+':\\s*([^\\n]+(?:\\n[^\\n:]{1,12}(?=\\n))?)'));return m?m[1].replace(/\n/g,' ').replace(/\s+/g,' ').trim():''};const ini=pd(g('Início')),fim=pd(g('Fim'))||ini;if(!ini)continue;
// programação contínua de meses (ex.: "Lazer no Parque", sala de jogos) não é evento; exposições ficam
if((fim.iso-ini.iso)/864e5>90&&c.cat!=='Exposições')continue;
const loc=g('Local').replace(/ ?Ver no mapa$/,''),end=g('Endereço').replace(/ ?Ver no mapa$/,'').replace(/,\s*$/,'');const pr=/Evento Gratuito/.test(t)?'Gratuito':/Evento Pago/.test(t)?'Pago':'';const im=d.querySelector('meta[property="og:image"]')?.content||'';const h=ini.h&&ini.h!=='00:00'?ini.h:'';
out.push([c.u.replace(/^\/evento\//,''),(d.querySelector('meta[property="og:title"]')?.content||c.t).trim(),ini.d===fim.d?ini.d:`${ini.d} a ${fim.d}`,h,end?`${loc}|${end}`:loc,pr,'',im,c.cat]);}catch(e){}}
JSON.stringify(out)
