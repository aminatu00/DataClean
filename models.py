from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    
    # Relation avec les fichiers nettoyés
    files = db.relationship('CleanedFile', backref='user', lazy=True)

class CleanedFile(db.Model):
    __tablename__ = 'cleaned_files'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    original_name = db.Column(db.String(255))
    filename = db.Column(db.String(255))
    cleaned_at = db.Column(db.DateTime, default=datetime.utcnow)
