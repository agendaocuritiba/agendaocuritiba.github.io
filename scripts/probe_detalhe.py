"""Olha em detalhe as respostas do Teatro Guaíra, Shotgun e Ticketmaster (cliente HTTP simples)."""
import re, time, urllib.request
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
def get(u):
    req = urllib.request.Request(u, headers={'User-Agent': UA, 'Accept-Language': 'pt-BR,pt;q=0.9', 'Accept': 'text/html,*/*'})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, dict(r.headers), r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode('utf-8', 'replace')
st, h, s = get('https://www.teatroguaira.pr.gov.br/calendario-eventos')
print('GUAIRA', st, 'ldjson', s.count('ld+json'), 'datas', re.findall(r'\d{2}/\d{2}/\d{4}', s)[:15])
for x in sorted(set(re.findall(r'href="([^"#]+)"', s))):
    if 'teatroguaira' in x or x.startswith('/'):
        print('  ', x)
for name, u in [('SHOTGUN', 'https://shotgun.live/pt-br/cities/curitiba'), ('TICKETMASTER', 'https://www.ticketmaster.com.br/')]:
    st, h, s = get(u)
    print(name, st, {k: v for k, v in h.items() if k.lower() in ('server', 'retry-after', 'cf-ray', 'x-vercel-mitigated', 'x-vercel-id', 'content-type', 'set-cookie')})
    print('   title', (re.search(r'<title>(.*?)</title>', s, re.S) or [0, ''])[1][:100], '| corpo', re.sub(r'\s+', ' ', s[:200]))
    if st == 429:
        print('   Retry-After:', h.get('Retry-After'), flush=True); time.sleep(60)
        st, h, s = get(u)
        print('   depois de esperar:', st, len(s))
