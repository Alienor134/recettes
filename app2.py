from flask import Flask, render_template, request, redirect, url_for
from tinydb import TinyDB
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static'
app.secret_key = 'alien_secret_key'  # Needed for flash messages if used

# Ensure folders exist
os.makedirs('data', exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Load database
db = TinyDB('data/recette_oeuf.json')

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
        lait_ml = request.form.get('lait_ml')
        temperature_C = request.form.get('temperature_C')
        duree_min = request.form.get('duree_min')

        # Handle image upload
        photo = request.files.get('photo')
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = 'default.jpg'  # fallback image

        # Save to DB
        recette = {
            'nombre_oeufs': int(nombre_oeufs),
            'beurre_gr': int(beurre_gr),
            'lait_L': float(lait_ml) / 1000,  # Convert ml to L
            'temperature_C': int(temperature_C),
            'duree_min': int(duree_min),
            'photo': filename
        }
        db.insert(recette)
        return redirect(url_for('index'))

    return render_template('add.html')

@app.route('/manage')
def manage():
    recettes = db.all()
    return render_template('manage.html', recettes=recettes)

@app.route('/edit/<int:doc_id>', methods=['GET', 'POST'])
def edit(doc_id):
    recette = db.get(doc_id=doc_id)
    if not recette:
        return "Recette introuvable", 404

    if request.method == 'POST':
        lait_ml = request.form.get('lait_ml')
        updated = {
            'nombre_oeufs': int(request.form.get('nombre_oeufs')),
            'beurre_gr': int(request.form.get('beurre_gr')),
            'lait_L': float(lait_ml) / 1000,
            'temperature_C': int(request.form.get('temperature_C')),
            'duree_min': int(request.form.get('duree_min')),
        }

        photo = request.files.get('photo')
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            updated['photo'] = filename

        db.update(updated, doc_ids=[doc_id])
        return redirect(url_for('manage'))

    return render_template('edit.html', recette=recette, doc_id=doc_id)

@app.route('/delete/<int:doc_id>')
def delete(doc_id):
    db.remove(doc_ids=[doc_id])
    return redirect(url_for('manage'))

if __name__ == '__main__':
    app.run(debug=True)
