import os
from flask import current_app
from werkzeug.utils import secure_filename

def save_staff_avatar(file):
    if not file:
        return None
    
    # Lấy upload folder từ config
    upload_folder = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        
    filename = secure_filename(file.filename) 
    file_path = os.path.join(upload_folder, f"staff_{filename}")