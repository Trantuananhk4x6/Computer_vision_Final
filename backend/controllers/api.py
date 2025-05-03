# Tạo endpoint mới trong file controllers/api.py để lấy danh sách video
from flask import Blueprint, request, jsonify, send_from_directory, current_app, Response
import os
import mimetypes
from werkzeug.utils import secure_filename
from services.tracking_service import TrackingService
from models.database import db, TrackingSession, Detection
from datetime import datetime, timedelta
import time
import re
import re
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from models.database import db, TrackingSession, Detection

# Create blueprint
api = Blueprint('api', __name__)

# Initialize tracking service
tracking_service = TrackingService()

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@api.route('/upload', methods=['POST'])
def upload_video():
    # Check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    # If user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Start processing the video
        result = tracking_service.process_video(filepath)
        
        return jsonify(result), 202
    
    return jsonify({'error': 'File type not allowed'}), 400

@api.route('/tracking/camera/start', methods=['POST'])
def start_camera_tracking():
    camera_id = request.json.get('camera_id', 0)  # Default to camera 0
    
    # Start camera tracking
    result = tracking_service.start_camera_tracking(camera_id)
    
    return jsonify(result), 202

@api.route('/tracking/camera/stop', methods=['POST'])
def stop_camera_tracking():
    session_id = request.json.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'Session ID required'}), 400
    
    # Stop camera tracking
    result = tracking_service.stop_camera_tracking(session_id)
    
    return jsonify(result)

@api.route('/tracking/status/<int:session_id>', methods=['GET'])
def get_tracking_status(session_id):
    # Get tracking status
    status = tracking_service.get_tracking_status(session_id)
    
    return jsonify(status)

@api.route('/sessions', methods=['GET'])
def get_sessions():
    # Get all tracking sessions
    sessions = tracking_service.get_all_sessions()
    
    return jsonify(sessions)

@api.route('/sessions/<int:session_id>', methods=['GET'])
def get_session_details(session_id):
    # Get session details
    session = tracking_service.get_session_details(session_id)
    
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify(session)

@api.route('/video/<path:filename>', methods=['GET'])
def get_video(filename):
    # Cấu hình content type và headers cho video streaming
    output_folder = current_app.config['OUTPUT_FOLDER']
    file_path = os.path.join(output_folder, filename)
    
    # Kiểm tra xem file có tồn tại không
    if not os.path.isfile(file_path):
        return jsonify({'error': 'Video file not found'}), 404
    
    # Xác định MIME type
    content_type, _ = mimetypes.guess_type(file_path)
    
    # Hỗ trợ byte range requests - cần thiết cho video streaming
    range_header = request.headers.get('Range', None)
    
    # Tính dung lượng file
    file_size = os.path.getsize(file_path)
    
    # Nếu có range header
    if range_header:
        # Phân tích range header
        byte1, byte2 = 0, None
        match = re.search(r'(\d+)-(\d*)', range_header)
        if match:
            groups = match.groups()
            if groups[0]: byte1 = int(groups[0])
            if groups[1]: byte2 = int(groups[1])
        
        # Nếu byte2 không được chỉ định, đọc đến cuối file
        if byte2 is None:
            byte2 = file_size - 1
        
        # Giới hạn byte2 để không vượt quá dung lượng file
        if byte2 >= file_size:
            byte2 = file_size - 1
        
        # Tính kích thước chunk
        chunk_size = byte2 - byte1 + 1
        
        # Mở file và đọc dữ liệu theo range
        with open(file_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(chunk_size)
        
        # Thiết lập response
        rv = Response(data, 206, mimetype=content_type, direct_passthrough=True)
        rv.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        rv.headers.add('Accept-Ranges', 'bytes')
        rv.headers.add('Content-Length', str(chunk_size))
        rv.headers.add('Cache-Control', 'no-cache, no-store, must-revalidate')
        rv.headers.add('Pragma', 'no-cache')
        rv.headers.add('Expires', '0')
        rv.headers.add('Access-Control-Allow-Origin', '*')
        rv.headers.add('Access-Control-Allow-Headers', 'Range')
        
        return rv
    else:
        # Nếu không có range header, sử dụng send_from_directory
        response = send_from_directory(output_folder, filename)
        response.headers.add('Accept-Ranges', 'bytes')
        response.headers.add('Content-Length', str(file_size))
        response.headers.add('Cache-Control', 'no-cache, no-store, must-revalidate')
        response.headers.add('Pragma', 'no-cache')
        response.headers.add('Expires', '0')
        response.headers.add('Access-Control-Allow-Origin', '*')
        
        return response

# Endpoint mới để lấy danh sách tất cả các video trong thư mục static/outputs
# @api.route('/videos', methods=['GET'])
# def list_videos():
#     """List all tracked videos"""
#     try:
#         # Đường dẫn tới thư mục chứa video
#         output_folder = current_app.config['OUTPUT_FOLDER']
        
#         if not os.path.exists(output_folder):
#             return jsonify([])
        
#         # Tất cả các file trong thư mục
#         files = os.listdir(output_folder)
        
#         # Lọc các file video (.mp4, .avi, v.v.)
#         video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
#         videos = []
        
#         for file in files:
#             file_path = os.path.join(output_folder, file)
#             if os.path.isfile(file_path) and any(file.lower().endswith(ext) for ext in video_extensions):
#                 # Lấy thông tin file
#                 file_stat = os.stat(file_path)
                
#                 # Xác định loại video
#                 video_type = 'tracked' if file.startswith('tracked_') else 'camera'
                
#                 videos.append({
#                     'filename': file,
#                     'size': file_stat.st_size,
#                     'created_date': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
#                     'type': video_type
#                 })
        
#         # Sắp xếp theo ngày tạo, mới nhất trước
#         videos.sort(key=lambda x: x['created_date'], reverse=True)
        
#         print(f"Found {len(videos)} videos in {output_folder}")
#         return jsonify(videos)
        
#     except Exception as e:
#         print(f"Error listing videos: {str(e)}")
#         return jsonify({'error': str(e)}), 500

@api.route('/stats/overview', methods=['GET'])
def get_stats_overview():
    # Get overall statistics
    total_sessions = TrackingSession.query.count()
    
    # Get total person and animal counts
    person_count = db.session.query(db.func.sum(Detection.count)).filter(
        Detection.class_name == 'person'
    ).scalar() or 0
    
    animal_count = db.session.query(db.func.sum(Detection.count)).filter(
        Detection.class_name.in_(['dog', 'cat', 'bird', 'horse', 'sheep', 'cow', 
                                 'elephant', 'bear', 'zebra', 'giraffe'])
    ).scalar() or 0
    
    # Get sessions from the last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_sessions = TrackingSession.query.filter(
        TrackingSession.start_time >= week_ago
    ).count()
    
    return jsonify({
        'total_sessions': total_sessions,
        'total_person_count': int(person_count),
        'total_animal_count': int(animal_count),
        'recent_sessions': recent_sessions
    })

@api.route('/stats/timeline', methods=['GET'])
def get_stats_timeline():
    # Get daily counts for the last 30 days
    days = int(request.args.get('days', 30))
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get daily person counts
    person_counts = db.session.query(
        db.func.date(Detection.timestamp).label('date'),
        db.func.sum(Detection.count).label('count')
    ).filter(
        Detection.timestamp >= start_date,
        Detection.class_name == 'person'
    ).group_by(
        db.func.date(Detection.timestamp)
    ).all()
    
    # Get daily animal counts
    animal_counts = db.session.query(
        db.func.date(Detection.timestamp).label('date'),
        db.func.sum(Detection.count).label('count')
    ).filter(
        Detection.timestamp >= start_date,
        Detection.class_name.in_(['dog', 'cat', 'bird', 'horse', 'sheep', 'cow', 
                                 'elephant', 'bear', 'zebra', 'giraffe'])
    ).group_by(
        db.func.date(Detection.timestamp)
    ).all()
    
    # Format for response
    person_data = {str(date): int(count) for date, count in person_counts}
    animal_data = {str(date): int(count) for date, count in animal_counts}
    
    # Create timeline data with all dates
    timeline = []
    for i in range(days):
        date = datetime.utcnow() - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        timeline.append({
            'date': date_str,
            'person_count': person_data.get(date_str, 0),
            'animal_count': animal_data.get(date_str, 0)
        })
    
    # Reverse to get chronological order
    timeline.reverse()
    
    return jsonify(timeline)
# Cập nhật controllers/api.py
@api.route('/video/<int:session_id>/delete', methods=['DELETE'])
def delete_video(session_id):
    """Delete a video and its associated data"""
    
    try:
        # Get session details
        session = TrackingSession.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        if not session.output_path:
            return jsonify({'error': 'No video associated with this session'}), 400
            
        # Get the video filename
        output_path = session.output_path
        filename = os.path.basename(output_path)
        
        # Delete the physical video file
        file_path = os.path.join(current_app.config['OUTPUT_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        # Delete detections associated with the session
        Detection.query.filter_by(session_id=session_id).delete()
        
        # Delete the session
        db.session.delete(session)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Video and associated data deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
    
    
@api.route('/videos', methods=['GET'])
@api.route('/videos/list', methods=['GET'])  # Hỗ trợ cả hai endpoint
def list_videos():
    """List all tracked videos"""
    try:
        # Đường dẫn tới thư mục chứa video
        output_folder = current_app.config['OUTPUT_FOLDER']
        
        print(f"Looking for videos in: {output_folder}")
        print(f"Folder exists: {os.path.exists(output_folder)}")
        
        if not os.path.exists(output_folder):
            return jsonify([])
        
        # Tất cả các file trong thư mục
        files = os.listdir(output_folder)
        
        print(f"Files found: {len(files)}")
        
        # Lọc các file video (.mp4, .avi, v.v.)
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
        videos = []
        
        for file in files:
            file_path = os.path.join(output_folder, file)
            if os.path.isfile(file_path) and any(file.lower().endswith(ext) for ext in video_extensions):
                # Lấy thông tin file
                file_stat = os.stat(file_path)
                
                # Xác định loại video
                video_type = 'tracked' if file.startswith('tracked_') else 'camera'
                
                # Tìm session_id từ tên file (nếu có)
                session_id = None
                detection_stats = None  # ĐẶT BIẾN NÀY Ở ĐÂY - TRƯỚC KHI SỬ DỤNG
                
                match = re.search(r'tracked_video_(\d+)\.mp4', file)
                if match:
                    session_id = int(match.group(1))
                    
                    # Lấy dữ liệu detection summary nếu có
                    try:
                        if session_id:
                            from models.database import TrackingSession, db  # Import tại đây để tránh circular import
                            session = db.session.query(TrackingSession).get(session_id)
                            if session and session.summary:
                                detection_stats = session.summary
                    except Exception as e:
                        print(f"Error getting detection stats: {e}")
                        pass
                
                video_info = {
                    'filename': file,
                    'size': file_stat.st_size,
                    'created_date': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                    'type': video_type,
                    'session_id': session_id
                }
                
                if detection_stats:
                    video_info['detection_stats'] = detection_stats
                
                videos.append(video_info)
        
        # Sắp xếp theo ngày tạo, mới nhất trước
        videos.sort(key=lambda x: x['created_date'], reverse=True)
        
        print(f"Returning {len(videos)} videos")
        return jsonify(videos)
        
    except Exception as e:
        print(f"Error listing videos: {str(e)}")
        return jsonify({'error': str(e)}), 500