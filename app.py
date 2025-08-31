"""
Recettes Flask App - Clean, maintainable, and robust
"""
import os
import json
import io
import requests
import hashlib
from flask import Flask, render_template, request, redirect, url_for, flash
from tinydb import TinyDB, JSONStorage
from tinydb.middlewares import CachingMiddleware
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static'
app.secret_key = 'alien_secret_key'
app.json.ensure_ascii = False
app.json.mimetype = "application/json; charset=utf-8"
os.makedirs('data', exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- TinyDB Setup ---
class UTF8Storage(JSONStorage):
    """Custom TinyDB storage to enforce UTF-8 encoding."""
    def __init__(self, path, create_dirs=False):
        super().__init__(path, create_dirs=create_dirs)
    def _open(self, mode):
        return io.open(self._handle, mode, encoding='utf-8')

db = TinyDB(
    'data/recettes_export.json',
    storage=UTF8Storage
)


def get_ingredient_choices(recettes):
    """Extract unique ingredient names and units from all recipes, separated by type."""
    unite_choices = set()
    quantite_choices = set()
    for r in recettes:
        # Pour ingrédients à l'unité
        if 'ingredients_unite' in r:
            for ing in r['ingredients_unite']:
                unite_choices.add((ing['nom'], ''))
        # Pour ingrédients en quantité
        if 'ingredients_quantite' in r:
            for ing in r['ingredients_quantite']:
                unite = ing.get('unite', '')
                quantite_choices.add((ing['nom'], unite))
    return sorted(list(unite_choices)), sorted(list(quantite_choices))


def save_photo(photo, recette_index=None, photo_num=None):
    """Save uploaded photo and return filename with custom format."""
    if photo and photo.filename != '':
        ext = os.path.splitext(photo.filename)[1]
        # Format: {recette_index}_{photo_num}.ext
        if recette_index is not None and photo_num is not None:
            filename = f"{recette_index}_{photo_num}{ext}"
        else:
            filename = secure_filename(photo.filename)
        photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None

def export_json_utf8():
    """Export TinyDB data with accents (not escaped) for backup."""
    with open('data/recettes_export_utf8.json', 'w', encoding='utf-8') as f:
        json.dump(db.storage.read(), f, ensure_ascii=False, indent=2)

def parse_hellofresh(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    # Nom de la recette
    nom = soup.find('h1')
    nom = nom.text.strip() if nom else url

    # Ingrédients
    ingredients = []
    for ing in soup.select('[data-test-id="ingredient-item"]'):
        nom_ing = ing.find('span', class_='ingredient-name')
        quantite_span = ing.find('span', class_='ingredient-amount')
        quantite_txt = quantite_span.text.strip() if quantite_span else ''
        # Sépare quantité et unité si possible (ex: "400 g" -> "400", "g")
        quantite, unite = '', ''
        if quantite_txt:
            import re
            match = re.match(r"^(\d+(?:[.,]\d+)?)\s*(.*)$", quantite_txt)
            if match:
                quantite = match.group(1)
                unite = match.group(2).strip()
            else:
                quantite = quantite_txt
        ingredients.append({
            'nom': nom_ing.text.strip() if nom_ing else '',
            'quantite': quantite,
            'unite': unite
        })

    # Photo principale : cherche balise meta og:image, puis img avec thumbnail/main dans src
    img_url = ''
    meta_img = soup.find('meta', property='og:image')
    if meta_img and meta_img.get('content'):
        img_url = meta_img['content']
    else:
        # Cherche une image avec "thumbnail" ou "main" dans le src
        img_candidates = soup.find_all('img')
        for img in img_candidates:
            src = img.get('src', '')
            if 'thumbnail' in src or 'main' in src or 'high' in src:
                img_url = src
                break
        # Fallback: prend la première image si rien trouvé
        if not img_url and img_candidates:
            img_url = img_candidates[0].get('src', '')
    photos = [img_url] if img_url else []

    return nom, ingredients, photos

def parse_marmiton(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    # Nom de la recette
    nom = soup.find('h1')
    nom = nom.text.strip() if nom else url

    # Ingrédients
    ingredients = []
    for ing in soup.select('.recipe-ingredients__list__item'):
        txt = ing.text.strip()
        # Extraction quantité/unité/nom par regex (ex: "200 g farine")
        import re
        match = re.match(r"^(\d+(?:[.,]\d+)?)\s*([^\d\s]+)?\s*(.*)$", txt)
        if match:
            quantite = match.group(1)
            unite = match.group(2) if match.group(2) else ''
            nom_ing = match.group(3).strip() if match.group(3) else txt
        else:
            quantite = ''
            unite = ''
            nom_ing = txt
        ingredients.append({'nom': nom_ing, 'quantite': quantite, 'unite': unite})

    # Photo principale : balise meta og:image ou première image de la recette
    img_url = ''
    meta_img = soup.find('meta', property='og:image')
    if meta_img and meta_img.get('content'):
        img_url = meta_img['content']
    else:
        img = soup.find('img', class_='recipe-media__img')
        if img and img.has_attr('src'):
            img_url = img['src']
    photos = [img_url] if img_url else []

    return nom, ingredients, photos

def get_recette_hash(nom):
    """Return a short hash for the recipe name."""
    return hashlib.sha1(nom.encode('utf-8')).hexdigest()[:8]

# --- Routes ---
@app.route('/')
def index():
    """Home page: list all recipes."""
    recettes = db.all()
    q = request.args.get('q', '').strip().lower()
    if q:
        def match(recette):
            # Cherche dans le nom
            if 'nom' in recette and q in str(recette['nom']).lower():
                return True
            # Cherche dans les notes
            if 'notes' in recette and q in str(recette['notes']).lower():
                return True
            # Cherche dans les ingrédients à l'unité
            if 'ingredients_unite' in recette:
                for ing in recette['ingredients_unite']:
                    if 'nom' in ing and q in str(ing['nom']).lower():
                        return True
            # Cherche dans les ingrédients en quantité
            if 'ingredients_quantite' in recette:
                for ing in recette['ingredients_quantite']:
                    if 'nom' in ing and q in str(ing['nom']).lower():
                        return True
            return False
        recettes = [r for r in recettes if match(r)]
    return render_template('index.html', recettes=recettes)

@app.route('/recette/<int:doc_id>')
def recette_detail(doc_id):
    """Detailed recipe view."""
    recette = db.get(doc_id=doc_id)
    if not recette:
        flash("Recette introuvable", "danger")
        return redirect(url_for('index'))
    return render_template('recette.html', recette=recette, doc_id=doc_id)

@app.route('/add', methods=['GET', 'POST'])
def add():
    """Add a new recipe."""
    if request.method == 'POST':
        try:
            nom_recette = request.form.get('nom', '').strip()
            photos = []
            photo = request.files.get('photo')
            print("DEBUG photo:", photo)
            if photo and photo.filename != '':
                print("DEBUG photo.filename:", photo.filename)
                filename = save_photo(photo, recette_index='new', photo_num=0)
                print("DEBUG saved filename:", filename)
                photos.append(filename)
            # DEBUG: print raw ingredient fields
            print("DEBUG ingredients_unite_json:", request.form.get('ingredients_unite_json', ''))
            print("DEBUG ingredients_quantite_json:", request.form.get('ingredients_quantite_json', ''))
            # Defensive: if empty string, use []
            ingredients_unite_raw = request.form.get('ingredients_unite_json', '')
            if not ingredients_unite_raw.strip():
                ingredients_unite = []
            else:
                ingredients_unite = json.loads(ingredients_unite_raw)
            ingredients_quantite_raw = request.form.get('ingredients_quantite_json', '')
            if not ingredients_quantite_raw.strip():
                ingredients_quantite = []
            else:
                ingredients_quantite = json.loads(ingredients_quantite_raw)
            recette = {
                'nom': nom_recette,
                'hash': get_recette_hash(nom_recette),
                'notes': request.form.get('notes', '').strip(),
                'ingredients_unite': ingredients_unite,
                'ingredients_quantite': ingredients_quantite,
                'photos': photos
            }
            doc_id = db.insert(recette)
            print("DEBUG doc_id:", doc_id)
            # Renomme la photo si besoin avec le vrai doc_id
            if photos:
                ext = os.path.splitext(photos[0])[1]
                # Ajoute le hash dans le nom du fichier
                new_filename = f"{doc_id}_{get_recette_hash(nom_recette)}_0{ext}"
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], photos[0])
                new_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                print("DEBUG rename:", old_path, "->", new_path)
                os.rename(old_path, new_path)
                recette['photos'][0] = new_filename
                db.update({'photos': recette['photos']}, doc_ids=[doc_id])
            flash("Recette ajoutée avec succès", "success")
            return redirect(url_for('index'))
        except Exception as e:
            print("DEBUG Exception:", e)
            flash(f"Erreur lors de l'ajout : {e}", "danger")
    recettes = db.all()
    ingredient_choices_unite, ingredient_choices_quantite = get_ingredient_choices(recettes)
    return render_template(
        'add.html',
        recettes=recettes,
        ingredient_choices_unite=ingredient_choices_unite,
        ingredient_choices_quantite=ingredient_choices_quantite
    )

@app.route('/manage')
def manage():
    """Manage recipes."""
    recettes = db.all()
    return render_template('manage.html', recettes=recettes)

@app.route('/edit/<int:doc_id>', methods=['GET', 'POST'])
def edit(doc_id):
    """Edit a recipe."""
    recette = db.get(doc_id=doc_id)
    if not recette:
        flash("Recette introuvable", "danger")
        return redirect(url_for('manage'))
    if request.method == 'POST':
        try:
            nom_recette = request.form.get('nom', '').strip()
            notes_raw = request.form.get('notes', '').strip()
            notes = json.dumps(notes_raw, ensure_ascii=True)[1:-1]
            updated = {
                'nom': nom_recette,
                'hash': get_recette_hash(nom_recette),
                'notes': notes,
                'ingredients_unite': json.loads(request.form.get('ingredients_unite_json', '[]')),
                'ingredients_quantite': json.loads(request.form.get('ingredients_quantite_json', '[]')),
                'photos': recette.get('photos', [])
            }
            photo = request.files.get('photo')
            if photo and photo.filename != '':
                photo_num = len(updated['photos'])
                ext = os.path.splitext(photo.filename)[1]
                filename = f"{doc_id}_{get_recette_hash(nom_recette)}_{photo_num}{ext}"
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                updated['photos'].append(filename)
            db.update(updated, doc_ids=[doc_id])
            flash("Recette modifiée avec succès", "success")
            return redirect(url_for('manage'))
        except Exception as e:
            flash(f"Erreur lors de la modification : {e}", "danger")
    recettes = db.all()
    ingredient_choices_unite, ingredient_choices_quantite = get_ingredient_choices(recettes)
    return render_template(
        'edit.html',
        recette=recette,
        doc_id=doc_id,
        ingredient_choices_unite=ingredient_choices_unite,
        ingredient_choices_quantite=ingredient_choices_quantite
    )

@app.route('/delete/<int:doc_id>')
def delete(doc_id):
    """Delete a recipe."""
    try:
        db.remove(doc_ids=[doc_id])
        flash("Recette supprimée", "success")
    except Exception as e:
        flash(f"Erreur lors de la suppression : {e}", "danger")
    return redirect(url_for('manage'))

@app.route('/add_from_url', methods=['GET', 'POST'])
def add_from_url():
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        recette = {'nom': '', 'ingredients': [], 'photos': [], 'notes': '', 'url': url}
        if 'hellofresh' in url:
            print("TRYING TO PARSE HELLOFRESH")
            nom, ingredients, photos = parse_hellofresh(url)
            recette['nom'] = nom
            recette['hash'] = get_recette_hash(nom)
            recette['ingredients'] = ingredients
            recette['photos'] = photos
            recette['notes'] = f'Recette importée depuis HelloFresh\n{url}'
        elif 'marmiton.org' in url or 'marmiton.fr' in url:
            nom, ingredients, photos = parse_marmiton(url)
            recette['nom'] = nom
            recette['hash'] = get_recette_hash(nom)
            recette['ingredients'] = ingredients
            recette['photos'] = photos
            recette['notes'] = f'Recette importée depuis Marmiton\n{url}'
        else:
            recette['nom'] = url
            recette['hash'] = get_recette_hash(url)
            recette['notes'] = f'Recette à compléter\n{url}'
        db.insert(recette)
        flash("Recette ajoutée depuis le lien", "success")
        return redirect(url_for('index'))
    return render_template('add_from_url.html')

if __name__ == '__main__':
    app.run(debug=True)

