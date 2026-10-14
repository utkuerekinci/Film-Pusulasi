"""Önceden Wikidata/Vikipedi'den indirilen bilgileri bağımsız film verisine dönüştür.

KULLANIM:
  python acik_veriyi_hazirla.py
  python acik_veriyi_hazirla.py --offline

Eski tmdb_5000_movies.csv okunmaz, kullanılmaz ve çıktı dosyasına konulmaz.
Wikimedia önbelleğinin kaydındaki sayısal eşleştirme anahtarı yalnızca geçmiş
indirme kaydını tanımak içindir; yayımlanan veri kaydına eklenmez.
"""

import argparse
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, unquote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
KAYNAK = ROOT / 'wikimedia_turkce.jsonl'
HEDEF = ROOT / 'filmler_acik_veri.json'
WIKIDATA_SPARQL = 'https://query.wikidata.org/sparql'
KIMLIK = re.compile(r'(Q[1-9][0-9]*)$')


def sade(metin):
    tr = str.maketrans({'ı':'i','ğ':'g','ü':'u','ş':'s','ö':'o','ç':'c'})
    return unicodedata.normalize('NFKD', str(metin or '').replace('İ','i').lower()).translate(tr)


# Bilinen genre etiketleri (Wikidata P136'da kullanılan Türkçe/İngilizce adlar).
# Bilinmeyen etiketlere tahmini bir tür atamak yerine listeyi boş bırakırız.
TUR_IFADELERI = {
 'Korku': ['horror','korku','slasher','supernatural horror','zombie film','zombi filmi'],
 'Komedi': ['comedy','komedi','parody','parodi','satire','hiciv','farce'],
 'Gerilim': ['thriller','gerilim','suspense'],
 'Bilim Kurgu': ['science fiction','sci fi','sci-fi','bilim kurgu','cyberpunk'],
 'Romantik': ['romance','romantic','romantik','ask filmi','love film'],
 'Aksiyon': ['action','aksiyon','martial arts'],
 'Macera': ['adventure','macera'],
 'Fantastik': ['fantasy','fantastik','fairy tale','masal'],
 'Dram': ['drama','dram','melodrama','tragedy'],
 'Suç': ['crime','suc','gangster','detective'],
 'Gizem': ['mystery','gizem'],
 'Animasyon': ['animation','animated','animasyon','anime'],
 'Aile': ['family','aile filmi'],
 'Belgesel': ['documentary','belgesel'],
 'Tarih': ['historical','tarih'],
 'Savaş': ['war film','savas filmi','military film'],
 'Müzik': ['musical','muzikal','music film','muzik filmi'],
 'Western': ['western','kovboy'],
}


def turleri_cevir(etiketler):
    sonuc = set()
    for etiket in etiketler:
        deger = sade(etiket).replace('-', ' ')
        # "comedy horror film" hem komedi hem korku; sonuçlar bu ayrımı korur.
        for hedef, terimler in TUR_IFADELERI.items():
            if any(re.search(r'(?<![a-z])'+re.escape(sade(t).replace('-', ' '))+r'(?![a-z])', deger) for t in terimler):
                sonuc.add(hedef)
    return sorted(sonuc)


def oku():
    if not KAYNAK.exists():
        raise SystemExit('HATA: wikimedia_turkce.jsonl dosyası bulunamadı. Önceden 4.803 filmi işlediğin dosyayı proje klasöründe tut.')
    kayitlar = {}
    with KAYNAK.open(encoding='utf-8') as f:
        for satir in f:
            try:
                rec = json.loads(satir)
            except (ValueError, TypeError):
                continue
            link = rec.get('wikidata_url','')
            match = KIMLIK.search(link)
            if match:
                qid = match.group(1)
                kayitlar[qid] = {
                    'wikidata_id': qid,
                    'wikidata_url': 'https://www.wikidata.org/wiki/' + qid,
                    'ad': str(rec.get('title','')).strip(),
                    'aciklama': str(rec.get('intro','')).strip(),
                    'kisa_bilgi': str(rec.get('description','')).strip(),
                    'wikipedia_url': str(rec.get('wikipedia_url','')).strip(),
                    'turler': [], 'yil': '', 'kaynak_turler': [],
                }
    return kayitlar


def getir(qids, agent):
    values = ' '.join('wd:' + qid for qid in qids)
    sparql = '''PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?film ?ad_tr ?ad_en ?tur ?tur_tr ?tur_en ?tarih WHERE {
  VALUES ?film { %s }
  OPTIONAL { ?film rdfs:label ?ad_tr. FILTER(LANG(?ad_tr) = "tr") }
  OPTIONAL { ?film rdfs:label ?ad_en. FILTER(LANG(?ad_en) = "en") }
  OPTIONAL {
    ?film wdt:P136 ?tur.
    OPTIONAL { ?tur rdfs:label ?tur_tr. FILTER(LANG(?tur_tr) = "tr") }
    OPTIONAL { ?tur rdfs:label ?tur_en. FILTER(LANG(?tur_en) = "en") }
  }
  OPTIONAL { ?film wdt:P577 ?tarih }
}''' % values
    url = WIKIDATA_SPARQL + '?' + urlencode({'query': sparql, 'format': 'json'})
    for attempt in range(5):
        try:
            req = Request(url, headers={'User-Agent': agent, 'Accept':'application/sparql-results+json'})
            with urlopen(req, timeout=55) as res:
                return json.load(res)['results']['bindings']
        except HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise RuntimeError('Wikidata HTTP '+str(e.code)) from e
            delay = e.headers.get('Retry-After', '')
            time.sleep(min(60, int(delay)) if delay.isdigit() else 5*(attempt+1))
        except (URLError, TimeoutError):
            time.sleep(4*(attempt+1))
    raise RuntimeError('Wikidata bağlantısı şu anda yanıt vermiyor. Biraz sonra tekrar dene.')


def zenginlestir(kayitlar, contact=''):
    ids = list(kayitlar)
    print(f'Önceden indirdiğin Wikimedia dosyasında {len(ids)} Wikidata film kaydı bulundu.')
    agent = 'BBY261FilmPusulasi/2.0 (student noncommercial project; '+(contact or 'github.com')+') Python-urllib'
    for offset in range(0, len(ids), 20):
        grup = ids[offset:offset+20]
        try:
            satirlar = getir(grup, agent)
        except RuntimeError as err:
            print('UYARI:', err, 'Kalan veriler çevrimdışı kullanılacak.')
            break
        for b in satirlar:
            def val(k): return b.get(k,{}).get('value','')
            qid_match = KIMLIK.search(val('film'))
            if not qid_match: continue
            qid = qid_match.group(1)
            rec = kayitlar.get(qid)
            if not rec: continue
            if val('ad_tr'): rec['ad'] = val('ad_tr')
            elif not rec['ad'] and val('ad_en'): rec['ad'] = val('ad_en')
            if val('tarih') and not rec['yil']:
                rec['yil'] = val('tarih')[:4]
            for key in ('tur_tr', 'tur_en'):
                if val(key): rec['kaynak_turler'].append(val(key))
        print(f'Wikidata türleri kontrol ediliyor: {min(offset+20,len(ids))}/{len(ids)}')
        time.sleep(0.8)


def giristen_turler(metin):
    """Wikidata geçici ulaşılamazsa yalnızca açık genre ifadelerini yakala.

    Tahmini film içeriği veya film ADI üzerinden tür çıkarılmaz.
    """
    bolum = sade(metin[:500])
    kaliplar = {
        'Korku': (r'korku (filmi|turunde|turu|yapimi)', r'(?<![a-z])horror film'),
        'Komedi': (r'komedi (filmi|turunde|turu|yapimi)', r'(?<![a-z])comedy film'),
        'Bilim Kurgu': (r'bilim kurgu (filmi|turunde|turu|yapimi)',r'(?<![a-z])science fiction film'),
        'Romantik': (r'romantik (komedi|dram|film)', r'(?<![a-z])romance film'),
        'Aksiyon': (r'aksiyon (filmi|turu|turunde)', r'(?<![a-z])action film'),
        'Animasyon': (r'animasyon (filmi|turu|turunde)',r'(?<![a-z])animated film'),
        'Gerilim': (r'gerilim (filmi|turu|turunde)',r'(?<![a-z])thriller film'),
        'Dram': (r'dram (filmi|turu|turunde)',r'(?<![a-z])drama film'),
        'Belgesel': (r'belgesel (film|yapim)',r'(?<![a-z])documentary film'),
        'Macera': (r'macera (filmi|turu|turunde)',r'(?<![a-z])adventure film'),
    }
    return sorted(k for k, patterns in kaliplar.items() if any(re.search(p,bolum) for p in patterns))


def kaydet(kayitlar):
    filmler = []
    for rec in kayitlar.values():
        title = rec['ad']
        if not title and '/wiki/' in rec['wikipedia_url']:
            title = unquote(urlsplit(rec['wikipedia_url']).path.split('/wiki/',1)[1]).replace('_',' ')
        if not title: continue
        rec['ad'] = title
        rec['turler'] = turleri_cevir(rec.pop('kaynak_turler', []))
        if not rec['turler']:
            rec['turler'] = giristen_turler(rec['aciklama'] + ' ' + rec['kisa_bilgi'])
        if not rec['aciklama'] and rec['kisa_bilgi']:
            rec['aciklama'] = rec['kisa_bilgi']
        if not rec['aciklama'] and not rec['turler']:
            continue
        # Wikipedia metni olan kayıtlarda bağlantı ve lisans bilgisi saklanır.
        rec['lisans'] = 'CC BY-SA 4.0' if rec['wikipedia_url'] and rec['aciklama'] != rec['kisa_bilgi'] else 'CC0 (Wikidata)'
        filmler.append(rec)
    filmler.sort(key=lambda r: r['ad'].casefold())
    HEDEF.write_text(json.dumps(filmler,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'BAŞARILI: {len(filmler)} film -> {HEDEF.name}')
    print('TMDB CSV dosyası KULLANILMADI. İçerik Wikidata ve varsa Vikipedi üzerinden elde edildi.')
    print('Bazı film kayıtlarının türü veya Türkçe özeti mevcut olmayabilir.')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--offline',action='store_true',help='Yeni sorgu yapmadan eldeki Türkçe verilerle çalış')
    p.add_argument('--contact',default='',help='Wikidata için iletişim adresi (isteğe bağlı)')
    args=p.parse_args()
    records=oku()
    if not records: raise SystemExit('HATA: Önbellekte Wikidata ile eşleşmiş film kaydı bulunamadı.')
    if not args.offline: zenginlestir(records,args.contact)
    kaydet(records)

if __name__=='__main__': main()
