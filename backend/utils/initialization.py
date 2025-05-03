import os
import shutil
from pathlib import Path

def initialize_directories(app):
    """Create necessary directories for the application"""
    
    # Create upload folder
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    
    # Create output folder for processed videos
    output_folder = app.config['OUTPUT_FOLDER']
    os.makedirs(output_folder, exist_ok=True)
    
    # Create models folder if it doesn't exist
    models_folder = os.path.join(os.path.dirname(app.config['MODEL_PATH']), '')
    os.makedirs(models_folder, exist_ok=True)
    
    # Check if DeepSORT model exists
    deepsort_model_dir = os.path.join('deep_sort_pytorch', 'deep_sort', 'deep', 'checkpoint')
    os.makedirs(deepsort_model_dir, exist_ok=True)
    
    # Log initialization
    app.logger.info('Application directories initialized')
    
    return True