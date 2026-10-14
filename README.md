# Film Pusulası — BBY261

Türkçe film öneri web uygulaması: Python + Flask + Gensim TF-IDF. Film verileri Wikidata CC0 ve Türkçe Vikipedi CC BY-SA 4.0 kaynaklıdır. **TMDB CSV kullanılmaz.**

## Kurulum (Windows, Python 3.12)

1. Bu dosyaları, eski projedeki `.venv` ve `wikimedia_turkce.jsonl` dosyasının bulunduğu klasöre kopyalayın. Eski `tmdb_5000_movies.csv` dosyası gereksizdir; silinebilir ve GitHub'a yüklenmemelidir.
2. Bir kere çalıştırın:

```powershell
.\.venv\Scripts\python.exe acik_veriyi_hazirla.py
```

Wikidata'nın film türlerini (P136) sorgular; API anahtarı gerekmez. İnternet ve Wikidata'nın yanıt hızına göre bir süre alabilir. Olur da servis yanıt vermezse **`--offline`** seçeneğiyle mevcut Vikipedi girişlerini kullanarak veri dosyası üretilir, ama tür filtresi zayıflar. Bu komut `filmler_acik_veri.json` dosyasını oluşturur. **Bu dosyayı GitHub'a yükleyin.**

3. Uygulamayı çalıştırın:

```powershell
.\.venv\Scripts\python.exe app.py
```

Tarayıcıda http://127.0.0.1:5000 açın. "Korku filmi", "uzayda macera" gibi aramalarla deneyin.

## GitHub ve Vercel

GitHub'a yükleyin: `app.py`, `film_motoru.py`, `acik_veriyi_hazirla.py`, `arama_sozlugu.py`, `filmler_acik_veri.json`, `requirements.txt`, `.python-version`, `.gitignore`, `README.md`, `templates/index.html`.

Yüklemeyin: `.venv`, `wikimedia_turkce.jsonl` (ara önbellek), `tmdb_5000_movies.csv`, eski `turkce_verileri_indir.py` veya eski `wikimedia_turkce_ekle.py` (TMDB CSV ister). Vercel'de projeyi GitHub'dan Import edip Deploy yapın. Vercel yalnızca `filmler_acik_veri.json` dosyasını okur; canlı Wikidata bağlantısı gerektirmez.

## Film verileri ve lisans

- Wikidata film adları, türler, yıllar: CC0 — https://www.wikidata.org/wiki/Wikidata:Licensing
- Türkçe Vikipedi makale girişleri: CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/
- Film sonuçlarında Vikipedi makalelerine/yazar geçmişlerine ve lisans metnine bağlantı verilir. Açıklamalar Türkçe Vikipedi'den alıntıdır; kapsamlı konu özeti garantisi yoktur.
- Bütün filmlerin Türkçe adı veya açıklaması bulunmayabilir. Sadece gerçekten eşleşen Wikidata kayıtları kullanılır; sayı 4.803'ten az olabilir.
- Türü bilinmeyen filmler, belirli tür isteyen aramalarda önerilmez. "Korku filmi" araması komedi filmlerini önermemeye çalışır.

## Algoritma

1. `filmler_acik_veri.json` okunur.
2. Açıklamalar normalize edilir, İngilizce eşanlamlı kelimelerle desteklenir.
3. Gensim `Dictionary`, `TfidfModel` ve `SparseMatrixSimilarity` metinlerin benzerliğini hesaplar.
4. Açıkça tür yazıldıysa `Wikidata P136` tür alanına göre filtre uygulanır, kalan filmler TF-IDF benzerliğine göre sıralanır.
5. Flask HTML üzerinden arama ve sonuçları sunar.

Açık veri kaynağı bulunmasına rağmen bu basit anahtar kelime/TF-IDF önericisi anlamsal bir büyük dil modeli değildir ve her sonuç doğru olmayabilir.
