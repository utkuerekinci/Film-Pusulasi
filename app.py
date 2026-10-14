"""Film Pusulası — BBY261 Flask/Gensim Türkçe film öneri uygulaması."""
from flask import Flask, render_template, request
from film_motoru import FilmMotoru

app=Flask(__name__)
motor=FilmMotoru()

@app.route('/',methods=['GET','POST'])
def ana_sayfa():
    sorgu=request.form.get('sorgu','').strip()[:500] if request.method=='POST' else ''
    return render_template('index.html',sorgu=sorgu,arama_yapildi=bool(sorgu),
        filmler=motor.oner(sorgu) if sorgu else [],
        film_sayisi=len(motor.filmler),turkce_ozet_sayisi=motor.turkce_ozet_sayisi)

if __name__=='__main__':
    app.run(debug=True)
