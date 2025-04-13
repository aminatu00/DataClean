import os

basedir = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
CLEANED_FOLDER = os.path.join(basedir, 'cleaned')
ALLOWED_EXTENSIONS = {'csv','xml','json'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max