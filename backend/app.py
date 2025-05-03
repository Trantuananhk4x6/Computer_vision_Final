# Updated app.py file
from flask import Flask, send_from_directory
from flask_cors import CORS
import os
import logging
import re
import mimetypes
from models.database import db
from controllers.api import api
from config import Config
from utils.initialization import initialize_directories

def create_app():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log')
        ]
    )
    
    app = Flask(__name__, static_folder='static')
    app.config.from_object(Config)
    
    # Initialize extensions
    CORS(app)
    db.init_app(app)  # This line is critical - initializes SQLAlchemy with this app
    
    # Register blueprints
    app.register_blueprint(api, url_prefix='/api')
    
    # Create database tables INSIDE app context
    with app.app_context():
        db.create_all()
        # Initialize application directories
        initialize_directories(app)
    
    # Serve static files with proper headers for videos
    @app.route('/static/<path:path>')
    def serve_static(path):
        if path.endswith(('.mp4', '.avi', '.mov', '.mkv')):
            # Special handling for video files
            file_path = os.path.join(app.static_folder, path)
            
            # Check if file exists
            if not os.path.isfile(file_path):
                return {'error': 'File not found'}, 404
                
            # Get file size and mime type
            file_size = os.path.getsize(file_path)
            content_type, _ = mimetypes.guess_type(file_path)
            
            # Handle range request for video streaming
            range_header = request.headers.get('Range', None)
            if range_header:
                byte1, byte2 = 0, None
                match = re.search(r'(\d+)-(\d*)', range_header)
                if match:
                    groups = match.groups()
                    if groups[0]: byte1 = int(groups[0])
                    if groups[1]: byte2 = int(groups[1])
                
                if byte2 is None:
                    byte2 = file_size - 1
                    
                if byte2 >= file_size:
                    byte2 = file_size - 1
                    
                length = byte2 - byte1 + 1
                
                response = send_from_directory(
                    app.static_folder, path, 
                    mimetype=content_type,
                    conditional=True
                )
                
                response.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
                response.headers.add('Accept-Ranges', 'bytes')
                response.headers.add('Content-Length', str(length))
                response.status_code = 206  # Partial content
                
                return response
        
        # Default handling for non-video files
        response = send_from_directory(app.static_folder, path)
        return response
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)