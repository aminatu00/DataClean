from flask import Flask, request, jsonify, send_file,render_template
from flask import Flask, render_template, redirect, url_for
import pandas as pd
import numpy as np
import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import MySQLdb.cursors
import re
from functools import wraps
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler



app = Flask(__name__)
def is_logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            return jsonify({'success': False, 'error': 'Authentification requise'}), 401
        return f(*args, **kwargs)
    return decorated_function

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  
app.config['MYSQL_PASSWORD'] = '' 
app.config['MYSQL_DB'] = 'python'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

app.config['CLEANED_FOLDER'] = 'cleaned_files'
os.makedirs(app.config['CLEANED_FOLDER'], exist_ok=True)


app.secret_key = 'votre_cle_secrete_super_securisee'

# Initialisation MySQL
mysql = MySQL(app)


# Configuration
UPLOAD_FOLDER = 'uploads'
CLEANED_FOLDER = 'cleaned'
# ALLOWED_EXTENSIONS = {'csv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLEANED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CLEANED_FOLDER'] = CLEANED_FOLDER

ALLOWED_EXTENSIONS = {'csv', 'txt', 'xml', 'json', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



def clean_data(df):
    """
    Nettoie le dataframe selon les règles spécifiées :
    1. Ne modifie pas la première colonne (ID)
    2. Normalise toutes les autres colonnes numériques
    3. Supprime les doublons
    4. Corrige les valeurs aberrantes
    """
    # Faire une copie profonde
    cleaned_df = df.copy(deep=True)
    
    # 1. Identifier et protéger la colonne ID (première colonne)
    id_col = cleaned_df.columns[0]
    print(f"Colonne ID identifiée : {id_col}")
    
    # Sauvegarder les ID originaux
    original_ids = cleaned_df[id_col].copy()
    
    # 2. Traitement des valeurs manquantes (sauf colonne ID)
    for col in cleaned_df.columns:
        if col != id_col:
            # Convertir les chaînes vides et espaces en NaN
            cleaned_df[col] = cleaned_df[col].replace(r'^\s*$', np.nan, regex=True)
            
            if cleaned_df[col].isna().sum() > 0:
                if pd.api.types.is_numeric_dtype(cleaned_df[col]):
                    # Imputation par la médiane
                    col_median = cleaned_df[col].median()
                    cleaned_df[col] = cleaned_df[col].fillna(col_median)
                else:
                    # Imputation par la valeur la plus fréquente
                    most_frequent = cleaned_df[col].mode()[0] if not cleaned_df[col].mode().empty else 'ValeurManquante'
                    cleaned_df[col] = cleaned_df[col].fillna(most_frequent)
    
    # 3. Suppression des doublons - version plus sûre
    before_count = len(cleaned_df)
    cleaned_df = cleaned_df[~cleaned_df.duplicated(subset=[id_col], keep='first')]
    after_count = len(cleaned_df)
    print(f"Doublons supprimés : {before_count - after_count}")
    
    # 4. Traitement des valeurs aberrantes (sauf colonne ID)
    numeric_cols = cleaned_df.select_dtypes(include=[np.number]).columns
    if id_col in numeric_cols:
        numeric_cols = numeric_cols.drop(id_col)
    
    for col in numeric_cols:
        # Calcul des bornes avec la méthode IQR
        Q1 = cleaned_df[col].quantile(0.25)
        Q3 = cleaned_df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # Remplacer les valeurs aberrantes
        cleaned_df[col] = np.where(cleaned_df[col] < lower_bound, lower_bound,
                                 np.where(cleaned_df[col] > upper_bound, upper_bound, cleaned_df[col]))
    
    # 5. Normalisation avec StandardScaler (sauf colonne ID)
    if len(numeric_cols) > 0:
        scaler = StandardScaler()
        # Sauvegarder les ID avant normalisation
        temp_ids = cleaned_df[id_col].copy()
        # Normaliser seulement les colonnes numériques
        cleaned_df[numeric_cols] = scaler.fit_transform(cleaned_df[numeric_cols])
        # Restaurer les ID originaux
        cleaned_df[id_col] = temp_ids
    
    # 6. Restaurer les ID originaux au cas où
    cleaned_df[id_col] = original_ids[:len(cleaned_df)]
    
    # 7. Réinitialiser l'index
    cleaned_df = cleaned_df.reset_index(drop=True)
    
    return cleaned_df
def detect_separator(file_path):
    """Détecte automatiquement le séparateur du fichier"""
    with open(file_path, 'r') as f:
        first_line = f.readline()
    
    # Liste des séparateurs possibles
    separators = [',', ';', '\t', '|', '-']
    
    for sep in separators:
        if sep in first_line:
            return sep
    
    # Par défaut, retourner la virgule
    return ','

def load_data(file_path):
    """Charge le fichier en détectant automatiquement le séparateur"""
    sep = detect_separator(file_path)
    print(f"Séparateur détecté : '{sep}'")
    
    try:
        # Essayer plusieurs encodages
        encodings = ['utf-8', 'latin1', 'ISO-8859-1', 'cp1252']
        for encoding in encodings:
            try:
                return pd.read_csv(file_path, sep=sep, encoding=encoding)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(file_path, sep=sep, encoding='utf-8', errors='ignore')
    except Exception as e:
        print(f"Erreur lors du chargement : {e}")
        raise
# @app.route('/api/clean', methods=['POST'])
# @is_logged_in
# def api_clean():
#     if 'file' not in request.files:
#         return jsonify({'success': False, 'error': 'Aucun fichier fourni'}), 400
    
#     file = request.files['file']
    
#     if file.filename == '':
#         return jsonify({'success': False, 'error': 'Nom de fichier vide'}), 400
    
#     if not allowed_file(file.filename):
#         return jsonify({'success': False, 'error': 'Type de fichier non autorisé'}), 400
    
#     try:
#         # Essayer d'abord avec UTF-8, puis avec d'autres encodages courants
#         try:
#             df = pd.read_csv(file, encoding='utf-8')
#         except UnicodeDecodeError:
#             try:
#                 file.seek(0)  # Réinitialiser le pointeur du fichier
#                 df = pd.read_csv(file, encoding='latin1')  # Plus permissif
#             except Exception as e:
#                 file.seek(0)
#                 df = pd.read_csv(file, encoding='ISO-8859-1')  # Autre encodage commun
        
#         # Nettoyage des données
#         cleaned_df = clean_data(df)
        
#         # Sauvegarde avec UTF-8 pour la cohérence
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         original_name = secure_filename(file.filename)
#         output_filename = f"cleaned_{timestamp}_{original_name}"
#         output_path = os.path.join(app.config['CLEANED_FOLDER'], output_filename)
        
#         cleaned_df.to_csv(output_path, index=False, encoding='utf-8')
        
#         # Enregistrement dans l'historique
#         cursor = mysql.connection.cursor()
#         cursor.execute("""
#             INSERT INTO cleaned_files (user_id, original_name, filename) 
#             VALUES (%s, %s, %s)
#         """, (session['id'], original_name, output_filename))
#         mysql.connection.commit()
        
#         return jsonify({
#             'success': True,
#             'message': 'Fichier nettoyé avec succès',
#             'filename': output_filename,
#             'original_name': original_name,
#             'columns': list(cleaned_df.columns),
#             'row_count': len(cleaned_df)
#         })
       
#     except Exception as e:
#         mysql.connection.rollback()
#         return jsonify({
#             'success': False,
#             'error': f"Erreur lors du traitement: {str(e)}"
#         }), 500

@app.route('/api/clean', methods=['POST'])
def api_clean():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier fourni'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nom de fichier vide'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Type de fichier non autorisé'}), 400
    
    try:
        # Essayer plusieurs encodages courants
        encodings_to_try = ['utf-8', 'latin1', 'ISO-8859-1', 'cp1252']
        
        for encoding in encodings_to_try:
            try:
                file.stream.seek(0)  # Réinitialiser le pointeur du fichier
                df = pd.read_csv(file, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return jsonify({
                'success': False,
                'error': "Impossible de décoder le fichier avec les encodages standards"
            }), 400
        
        # Le reste de votre traitement...
        cleaned_df = clean_data(df)
        
        filename = secure_filename(file.filename)
        output_filename = f"cleaned_{filename}"
        output_path = os.path.join(app.config['CLEANED_FOLDER'], output_filename)
        cleaned_df.to_csv(output_path, index=False, encoding='utf-8')
        
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO cleaned_files (user_id, original_name, filename) 
            VALUES (%s, %s, %s)
        """, (session['id'], file.filename, output_filename))  # Note: utiliser output_filename ici
        mysql.connection.commit()
        
        return jsonify({
            'success': True,
            'message': 'Fichier nettoyé avec succès',
            'filename': output_filename,
            'columns': list(cleaned_df.columns),
            'row_count': len(cleaned_df)
        })
       
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Erreur lors du traitement: {str(e)}"
        }), 500

# @app.route('/api/download/<filename>', methods=['GET'])
# def download_file(filename):
#     try:
#         return send_file(
#             os.path.join(app.config['CLEANED_FOLDER'], filename),
#             as_attachment=True,
#             mimetype='text/csv',
#             download_name=filename
#         )
#     except FileNotFoundError:
#         return jsonify({'success': False, 'error': 'Fichier non trouvé'}), 404


@app.route('/api/download/<filename>')
@is_logged_in
def download_file(filename):
    try:
        # Vérifier que le fichier appartient à l'utilisateur
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT filename, original_name FROM cleaned_files 
            WHERE user_id = %s AND filename = %s
        """, (session['id'], filename))
        
        file_data = cursor.fetchone()
        if not file_data:
            return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
        
        file_path = os.path.join(app.config['CLEANED_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'Fichier non trouvé'}), 404
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_data['original_name'],  # Utiliser le nom original
            mimetype='csv'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/')
def index():
    return render_template('home.html')
# route pour la conection et l'inscription

# Route pour la page de connexion
# Route Connexion



# Fonction pour vérifier si l'utilisateur est connecté
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'loggedin' in session:
            return f(*args, **kwargs)
        else:
            flash('Veuillez vous connecter', 'warning')
            return redirect(url_for('login'))
    return wrap

# Route Accueil


# Route Connexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        
        # Vérification dans la base de données
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            # Création de la session
            session['loggedin'] = True
            session['id'] = user['id']
            session['name'] = user['name']
            session['email'] = user['email']
            flash('Connexion réussie!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Email ou mot de passe incorrect', 'danger')
    
    return render_template('login.html')

# Route Inscription
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Validation
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas', 'danger')
        else:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            account = cursor.fetchone()
            
            if account:
                flash('Cet email est déjà utilisé', 'danger')
            elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
                flash('Adresse email invalide', 'danger')
            elif len(password) < 6:
                flash('Le mot de passe doit contenir au moins 6 caractères', 'danger')
            else:
                # Hachage du mot de passe
                hashed_password = generate_password_hash(password)
                
                # Insertion dans la base
                cursor.execute(
                    'INSERT INTO users (name, email, password) VALUES (%s, %s, %s)',
                    (name, email, hashed_password)
                )
                mysql.connection.commit()
                flash('Inscription réussie! Vous pouvez maintenant vous connecter', 'success')
                return redirect(url_for('login'))
    
    return render_template('register.html')

# Route Profil (protégée)
@app.route('/profile')
@is_logged_in
def profile():
    return render_template('profile.html', user={
        'name': session['name'],
        'email': session['email']
    })

# pour l'historique
@app.route('/api/history')
@is_logged_in
def api_history():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT original_name, filename, cleaned_at 
            FROM cleaned_files 
            WHERE user_id = %s 
            ORDER BY cleaned_at DESC
        """, (session['id'],))
        files = cursor.fetchall()
        
        # Formatage des dates pour JSON
        for file in files:
            file['cleaned_at'] = file['cleaned_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({'success': True, 'files': files})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Route Déconnexion
@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté', 'info')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)