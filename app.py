from flask import Flask, render_template, request, redirect, url_for
from tinydb import TinyDB
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static'

db = TinyDB('data/recette_oeuf.json')

print("yoyo")
@app.route('/')
def index():
    recettes = db.all()
    return render_template('index.html', recettes=recettes)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        # Get form data
        nombre_oeufs = request.form.get('nombre_oeufs')
        beurre_gr = request.form.get('beurre_gr')
        lait_mL = request.form.get('lait_mL')
        temperature_C = request.form.get('temperature_C')
        duree_min = request.form.get('duree_min')

        # Handle image upload
        photo = request.files.get('photo')
        if photo and photo.filename != '':
           photo_filename = secure_filename(photo.filename)
           photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
        # Save to DB
        recette = {
            'nombre_oeufs': int(nombre_oeufs),
            'beurre_gr': int(beurre_gr),
            'lait_mL': float(lait_mL),
            'temperature_C': int(temperature_C),
            'duree_min': int(duree_min),
            'photo': photo_filename
        }
        db.insert(recette)
        return redirect(url_for('index'))

    return render_template('add.html')


if __name__ == '__main__':
    app.run(debug=True)
