"""Testa se cada site de origem responde a um cliente HTTP simples (sem navegador)."""
import json, re, sys, urllib.request, urllib.parse, datetime

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
HOJE = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).strftime('%d-%m-%Y')


def get(url, data=None, headers=None):
    h = {'User-Agent': UA, 'Accept-Language': 'pt-BR,pt;q=0.9', 'Accept': '*/*'}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:
        return 0, repr(e)


def count(pat, s):
    return len(set(re.findall(pat, s)))


def jlen(s, key=None):
    try:
        j = json.loads(s)
        return len(j[key] if key else j) if not callable(key) else key(j)
    except Exception as e:
        return 'json? ' + s[:120].replace('\n', ' ')


tests = []
def t(name, fn):
    try:
        tests.append((name,) + fn())
    except Exception as e:
        tests.append((name, 0, 'erro ' + repr(e)))

def eventoon():
    st, s = get('https://www.eventoon.com.br/cidade/curitiba-pr')
    base = (re.search(r'data-baseurl="([^"]+)"', s) or [None, 'https://www.eventoon.com.br/'])[1]
    body = urllib.parse.urlencode({'offset': 1, 'artista': '', 'cidade': '2878', 'estado': '18'}).encode()
    st2, s2 = get(base + 'ListaEventos/getEventos', body, {'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'})
    return st2, 'pagina=%s base=%s pgs=%s eventos_pg1=%s' % (st, base, jlen(s2, lambda j: j.get('qtd_pgs')), count(r'/evento/[^"\']+', s2))
t('eventoon', eventoon)
t('turismo', lambda: (lambda r: (r[0], 'links=%d' % count(r'/evento/[^"\']+', r[1])))(get('https://turismo.curitiba.pr.gov.br/eventos/%s/1' % HOJE)))
t('disk', lambda: (lambda r: (r[0], 'hits=%s' % jlen(r[1], lambda j: len(j['hits']['hits']))))(get('https://www.diskingressos.com.br/home/_search?size=100&from=0', b'{}', {'Content-Type': 'application/json'})))
t('sympla', lambda: (lambda r: (r[0], 'links=%d' % count(r'sympla\.com\.br/evento/[^"\'?]+', r[1])))(get('https://www.sympla.com.br/eventos/curitiba-pr/show-musica-festa?page=1')))
t('blueticket', lambda: (lambda r: (r[0], 'eventos=%s' % jlen(r[1])))(get('https://api2-cdn.blueticket.com.br/events?city=Curitiba', headers={'Origin': 'https://www.blueticket.com.br', 'Referer': 'https://www.blueticket.com.br/'})))
t('bilheteria', lambda: (lambda r: (r[0], 'curitiba=%d tamanho=%d' % (r[1].count('Curitiba - PR'), len(r[1]))))(get('https://www.bilheteriadigital.com/PR/as/1')))
t('ingresse', lambda: (lambda r: (r[0], 'eventos=%s' % jlen(r[1], lambda j: len(j['events']))))(get('https://api-site.ingresse.com/events/search?company_id=1&size=100&order_by_date=true&offset=0')))
t('ticketmaster', lambda: (lambda r: (r[0], 'links=%d tamanho=%d' % (count(r'/event/[^"\'?#]+', r[1]), len(r[1]))))(get('https://www.ticketmaster.com.br/')))
t('fever', lambda: (lambda r: (r[0], 'links=%d itemlist=%s tamanho=%d' % (count(r'/m/\d+', r[1]), 'ItemList' in r[1], len(r[1]))))(get('https://feverup.com/pt/curitiba')))
t('ingressocom', lambda: (lambda r: (r[0], 'eventos=%s' % jlen(r[1], lambda j: len(j['events']))))(get('https://www.ingresso.com/api/events?event_type=&per_page=99999')))
t('shotgun', lambda: (lambda r: (r[0], 'links=%d tamanho=%d' % (count(r'/events/[^"\'?/]+', r[1]), len(r[1]))))(get('https://shotgun.live/pt-br/cities/curitiba')))
t('guaira', lambda: (lambda r: (r[0], 'links=%d tamanho=%d' % (count(r'href="[^"]*(?:evento|espetaculo)[^"]*"', r[1]), len(r[1]))))(get('https://www.teatroguaira.pr.gov.br/calendario-eventos')))

for row in tests:
    print('%-13s %s  %s' % row)
