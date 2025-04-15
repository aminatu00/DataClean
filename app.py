from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import pandas as pd
import numpy as np
import os
import re
from sklearn.preprocessing import StandardScaler
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime

# Initialisation de l'application
app = Flask(__name__)

# Configuration PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Admin@localhost:5432/python'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'votre_cle_secrete_super_securisee'

# Initialisation de la base de données
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Configuration des dossiers
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['CLEANED_FOLDER'] = 'cleaned_files'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CLEANED_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'csv', 'txt', 'xml', 'json', 'xls', 'xlsx'}

# Modèles de données
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    files = db.relationship('CleanedFile', backref='user', lazy=True)

class CleanedFile(db.Model):
    __tablename__ = 'cleaned_files'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    cleaned_at = db.Column(db.DateTime, default=datetime.utcnow)

# Décorateur d'authentification
def is_logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            return jsonify({'success': False, 'error': 'Authentification requise'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Fonctions utilitaires
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_data(df):
    """Nettoie le dataframe selon les règles spécifiées"""
    cleaned_df = df.copy(deep=True)
    id_col = cleaned_df.columns[0]
    original_ids = cleaned_df[id_col].copy()
    
    # Traitement des valeurs manquantes
    for col in cleaned_df.columns:
        if col != id_col:
            cleaned_df[col] = cleaned_df[col].replace(r'^\s*$', np.nan, regex=True)
            if cleaned_df[col].isna().sum() > 0:
                if pd.api.types.is_numeric_dtype(cleaned_df[col]):
                    cleaned_df[col] = cleaned_df[col].fillna(cleaned_df[col].median())
                else:
                    most_frequent = cleaned_df[col].mode()[0] if not cleaned_df[col].mode().empty else 'ValeurManquante'
                    cleaned_df[col] = cleaned_df[col].fillna(most_frequent)
    
    # Suppression des doublons
    cleaned_df = cleaned_df[~cleaned_df.duplicated(subset=[id_col], keep='first')]
    
    # Correction des valeurs aberrantes
    numeric_cols = cleaned_df.select_dtypes(include=[np.number]).columns
    if id_col in numeric_cols:
        numeric_cols = numeric_cols.drop(id_col)
    
    for col in numeric_cols:
        Q1 = cleaned_df[col].quantile(0.25)
        Q3 = cleaned_df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        cleaned_df[col] = np.where(cleaned_df[col] < lower_bound, lower_bound,
                                 np.where(cleaned_df[col] > upper_bound, upper_bound, cleaned_df[col]))
    
    # Normalisation
    if len(numeric_cols) > 0:
        scaler = StandardScaler()
        temp_ids = cleaned_df[id_col].copy()
        cleaned_df[numeric_cols] = scaler.fit_transform(cleaned_df[numeric_cols])
        cleaned_df[id_col] = temp_ids
    
    cleaned_df[id_col] = original_ids[:len(cleaned_df)]
    return cleaned_df.reset_index(drop=True)

# Routes d'authentification
@app.route('/')
def index():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['loggedin'] = True
            session['id'] = user.id
            session['name'] = user.name
            session['email'] = user.email
            flash('Connexion réussie!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Email ou mot de passe incorrect', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas', 'danger')
        else:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Cet email est déjà utilisé', 'danger')
            elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
                flash('Adresse email invalide', 'danger')
            elif len(password) < 6:
                flash('Le mot de passe doit contenir au moins 6 caractères', 'danger')
            else:
                hashed_password = generate_password_hash(password)
                new_user = User(name=name, email=email, password=hashed_password)
                db.session.add(new_user)
                db.session.commit()
                flash('Inscription réussie! Vous pouvez maintenant vous connecter', 'success')
                return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/profile')
@is_logged_in
def profile():
    return render_template('profile.html', user={
        'name': session['name'],
        'email': session['email']
    })

@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté', 'info')
    return redirect(url_for('index'))

# Routes API
@app.route('/api/clean', methods=['POST'])
@is_logged_in
def api_clean():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier fourni'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nom de fichier vide'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Type de fichier non autorisé'}), 400
    
    try:
        # Essayer plusieurs encodages
        encodings = ['utf-8', 'latin1', 'ISO-8859-1', 'cp1252']
        for encoding in encodings:
            try:
                file.stream.seek(0)
                df = pd.read_csv(file, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return jsonify({
                'success': False,
                'error': "Impossible de décoder le fichier avec les encodages standards"
            }), 400
        
        cleaned_df = clean_data(df)
        filename = secure_filename(file.filename)
        output_filename = f"cleaned_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        output_path = os.path.join(app.config['CLEANED_FOLDER'], output_filename)
        cleaned_df.to_csv(output_path, index=False, encoding='utf-8')
        
        # Enregistrement dans la base de données
        new_file = CleanedFile(
            user_id=session['id'],
            original_name=filename,
            filename=output_filename
        )
        db.session.add(new_file)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Fichier nettoyé avec succès',
            'filename': output_filename,
            'columns': list(cleaned_df.columns),
            'row_count': len(cleaned_df)
        })
       
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f"Erreur lors du traitement: {str(e)}"
        }), 500

@app.route('/api/download/<filename>')
@is_logged_in
def download_file(filename):
    try:
        file_record = CleanedFile.query.filter_by(
            user_id=session['id'],
            filename=filename
        ).first()
        
        if not file_record:
            return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
        
        file_path = os.path.join(app.config['CLEANED_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'Fichier non trouvé'}), 404
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_record.original_name,
            mimetype='text/csv'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history')
@is_logged_in
def api_history():
    try:
        files = CleanedFile.query.filter_by(
            user_id=session['id']
        ).order_by(CleanedFile.cleaned_at.desc()).all()
        
        files_data = [{
            'original_name': file.original_name,
            'filename': file.filename,
            'cleaned_at': file.cleaned_at.strftime('%Y-%m-%d %H:%M:%S')
        } for file in files]
        
        return jsonify({'success': True, 'files': files_data})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)