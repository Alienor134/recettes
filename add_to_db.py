from tinydb import TinyDB

# Création ou ouverture de la base
db = TinyDB('recette_oeuf.json')

# Première entrée
recette = {
    'nombre_oeufs': 4,
    'beurre_gr': 25,
    'lait_L': 0.02,
    'temperature_C': 90,
    'duree_min': 8,
    'photo': 'chemin/vers/la/photo.jpg'  # à adapter selon ton système
}

# Insertion dans la base
db.insert(recette)

print("Recette ajoutée avec succès !")

