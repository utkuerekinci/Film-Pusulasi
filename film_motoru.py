"""Wikidata/Vikipedi açık verisiyle Türkçe film önerme.

TF-IDF Gensim ile film açıklamalarını karşılaştırır; film türü isteğinde
Wikidata'dan gelen P136 türleri kesin filtre olarak kullanılır.
"""
import json
import math
import re
import unicodedata
from pathlib import Path
from gensim.corpora import Dictionary
from gensim.models import TfidfModel
from gensim.similarities import SparseMatrixSimilarity
from arama_sozlugu import KELIMELER, DURAK_KELIMELER

ROOT = Path(__file__).resolve().parent
VERI = ROOT / 'filmler_acik_veri.json'

TR_MAP = str.maketrans({'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c'})
ENG_STOP = {'the', 'and', 'for', 'with', 'that', 'from', 'were', 'was', 'are', 'this', 'into', 'their', 'they', 'who', 'how', 'has', 'had', 'have'}
EKLER = ('larımızdan', 'lerimizden', 'larından', 'lerinden', 'larında', 'lerinde', 'ların', 'lerin', 'lar', 'ler', 'den', 'dan', 'tan', 'ten', 'deki', 'daki', 'nde', 'nda', 'dan', 'den', 'nin', 'nın', 'unun', 'inin', 'dır', 'dir', 'tir', 'tır', 'miş', 'mış', 'mıs', 'muş', 'i', 'ı', 'u', 'ü', 'a', 'e')

# Bu isimler hem tür filtresinde hem öneride kullanılan gerçek tür alanlarıdır.
TUR_SOZLUGU = {
 'Korku': ['korku', 'korkunc', 'horror', 'scary'],
 'Komedi': ['komedi', 'komik', 'gulduren', 'comedy', 'funny'],
 'Gerilim': ['gerilim', 'thriller'],
 'Bilim Kurgu': ['bilim kurgu','bilimkurgu','science fiction','sci fi','sci-fi'],
 'Romantik': ['romantik','romantizm','romantic','romance'],
 'Aksiyon': ['aksiyon','action'], 'Macera': ['macera','adventure'],
 'Fantastik': ['fantastik','fantastical','fantasy'],
 'Dram': ['dram','drama','dramatik'], 'Suç': ['suc filmi','crime'],
 'Gizem': ['gizem','mystery'], 'Animasyon': ['animasyon','animation','anime'],
 'Aile': ['aile filmi','family movie'], 'Belgesel': ['belgesel','documentary'],
 'Tarih': ['tarihi film','history movie','historical'],
 'Savaş': ['savas filmi','war movie'], 'Müzik': ['muzikal','musical'],
 'Western': ['western','kovboy'],
}


def sade(metin):
    s = str(metin or '').replace('İ','i').lower().translate(TR_MAP)
    return ''.join(x for x in unicodedata.normalize('NFKD', s) if not unicodedata.combining(x))


DURAK = {sade(x) for x in DURAK_KELIMELER} | ENG_STOP | {
  'film','filmi','filmler','filmleri','filmin','istiyorum','oner','onerir','onerisi',
  'bana','bir','ve','ile','icin','gibi','olan','oldugu','aramaktayim','ariyorum',
  'gecen','hikaye','konulu','biraz','cok','olabilir','olsun','izlemek','izleyebilecegim',
}


def parcala(metin):
    return [k for k in re.findall('[a-z0-9]+', sade(metin)) if len(k)>2 and k not in DURAK]


ES_ANLAM = {sade(k):parcala(v) for k,v in KELIMELER.items() if ' ' not in k}
ES_KALIPLAR = {sade(k):parcala(v) for k,v in KELIMELER.items() if ' ' in k}


def genislet(metin):
    kelimeler = parcala(metin)
    sonuc = list(kelimeler)
    duz = ' ' + ' '.join(kelimeler) + ' '
    for kalip, ek in ES_KALIPLAR.items():
        if ' '+kalip+' ' in duz: sonuc.extend(ek)
    for k in kelimeler:
        aktar = ES_ANLAM.get(k)
        if not aktar:
            for ek in EKLER:
                end = sade(ek)
                if k.endswith(end) and len(k)-len(end)>=3 and k[:-len(end)] in ES_ANLAM:
                    aktar = ES_ANLAM[k[:-len(end)]]
                    break
        if aktar: sonuc.extend(aktar)
    return sonuc


def tur_istegi(sorgu):
    """Tür istediğinde film başlığına değil, ayrı tür alanına bakar."""
    s = sade(sorgu).replace('-',' ')
    diz = re.findall(r'[a-z0-9]+', s)
    kaliplar = []
    for tur, adlar in TUR_SOZLUGU.items():
        for ad in adlar:
            t = tuple(sade(ad).replace('-',' ').split())
            if t: kaliplar.append((t,tur))
    kaliplar.sort(key=lambda x:len(x[0]),reverse=True)
    istenen, haric, silinecek = set(), set(), set()
    i=0
    while i<len(diz):
        esles = next(((k,t) for k,t in kaliplar if tuple(diz[i:i+len(k)])==k),None)
        if not esles: i+=1;continue
        k,t = esles
        son = diz[i+len(k):i+len(k)+3]
        once = diz[max(0,i-2):i]
        olumsuz = any(x in {'istemiyorum','sevmiyorum','olmasin','haric','degil','istemem'} for x in son+once)
        if len(son)>1 and son[0] in {'film','filmi'} and son[1] in {'istemiyorum','olmasin','degil'}: olumsuz=True
        (haric if olumsuz else istenen).add(t)
        silinecek.update(range(i,i+len(k)))
        i+=len(k)
    istenen-=haric
    konu=' '.join(k for i,k in enumerate(diz) if i not in silinecek)
    return istenen,haric,konu


class FilmMotoru:
    def __init__(self):
        if not VERI.exists():
            raise RuntimeError('filmler_acik_veri.json eksik. Önce: .\\.venv\\Scripts\\python.exe acik_veriyi_hazirla.py')
        self.filmler = json.loads(VERI.read_text(encoding='utf-8'))
        if not self.filmler:
            raise RuntimeError('Açık veri dosyası boş. Önce acik_veriyi_hazirla.py çalıştır.')
        self.turkce_ozet_sayisi = sum(bool(f.get('aciklama')) for f in self.filmler)
        belgeler=[]
        for f in self.filmler:
            turler=' '.join(f.get('turler',[]))
            belge=(str(f.get('aciklama',''))[:1500]+' '+str(f.get('kisa_bilgi',''))+' '+(' '+turler)*4)
            belgeler.append(genislet(belge))
        self.sozluk=Dictionary(belgeler)
        korpus=[self.sozluk.doc2bow(k) for k in belgeler]
        self.tfidf=TfidfModel(korpus,normalize=True)
        self.indeks=SparseMatrixSimilarity(self.tfidf[korpus],num_features=max(1,len(self.sozluk)))

    def oner(self, sorgu, adet=5):
        istenen,haric,konu=tur_istegi((sorgu or '')[:500])
        adaylar=[]
        for i, f in enumerate(self.filmler):
            turler=set(f.get('turler',[]))
            if turler & haric: continue
            if istenen and not turler & istenen: continue
            # Korku isteyen kullanıcıya korku-komedi filmini önceliklendirmeyelim.
            if istenen == {'Korku'} and 'Komedi' in turler: continue
            adaylar.append(i)
        if not adaylar: return []
        words=genislet(konu)
        bow=self.sozluk.doc2bow(words)
        has_text=bool(bow)
        if not istenen and not has_text: return []
        sims=self.indeks[self.tfidf[bow]] if has_text else None
        results=[]
        for i in adaylar:
            f=self.filmler[i]
            turler=set(f.get('turler',[]))
            both=int(not istenen or istenen.issubset(turler))
            cosine=float(sims[i]) if has_text else 0.0
            has_intro=int(bool(f.get('wikipedia_url') and f.get('aciklama')))
            # Geniş sorguda bilgilendirici Türkçe metinleri öne al.
            metin_kalitesi=min(len(f.get('aciklama','')),450)/450
            quality=0.2*has_intro+0.8*metin_kalitesi
            score=cosine*0.90+quality*0.10 if has_text else quality
            results.append((both,score,i,cosine))
        results.sort(key=lambda a:(a[0],a[1]),reverse=True)
        return [{**self.filmler[i], 'benzerlik':round(cosine*100,1) if has_text else None,
                 'tur_eslesmesi':bool(istenen)} for _,_,i,cosine in results[:adet]]
