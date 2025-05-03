# scripts/update_detection_counts.py
import os
import sys
import json
from datetime import datetime
import cv2
from ultralytics import YOLO

# Thiết lập đường dẫn
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BACKEND_DIR)

from config import Config
from models.database import db, TrackingSession, Detection
from app import create_app

def count_objects_in_video(video_path, model_path):
    """Đếm số đối tượng trong video sử dụng YOLOv8"""
    model = YOLO(model_path)
    
    # Mở video file
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return None
    
    frame_count = 0
    person_count = 0
    animal_count = 0
    class_counts = {}
    
    # Danh sách ID đã theo dõi
    tracked_persons = set()
    tracked_animals = set()
    
    # Animal classes in COCO dataset
    animal_classes = {'dog', 'cat', 'bird', 'horse', 'sheep', 'cow', 
                      'elephant', 'bear', 'zebra', 'giraffe'}
    
    # Xử lý từng frame
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Chỉ xử lý mỗi 30 frames để tăng tốc độ
        if frame_count % 30 == 0:
            print(f"Processing frame {frame_count}...")
            
            # Get results from YOLO with tracking
            results = model.track(frame, persist=True)
            
            if results and len(results) > 0 and results[0].boxes is not None:
                boxes = results[0].boxes
                cls_ids = boxes.cls.cpu().numpy().astype(int)
                track_ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else None
                
                for i, cls_id in enumerate(cls_ids):
                    class_name = model.names[cls_id]
                    
                    # Cập nhật class counts
                    if class_name not in class_counts:
                        class_counts[class_name] = 0
                    class_counts[class_name] += 1
                    
                    # Track unique objects if IDs available
                    if track_ids is not None:
                        track_id = track_ids[i]
                        track_key = f"{class_name}_{track_id}"
                        
                        if class_name == 'person':
                            tracked_persons.add(track_key)
                        elif class_name in animal_classes:
                            tracked_animals.add(track_key)
        
        frame_count += 1
        
        # Check for early termination
        if frame_count > 1000:  # Limit to 1000 frames for efficiency
            break
    
    # Giải phóng tài nguyên
    cap.release()
    
    # Tính tổng số đối tượng duy nhất
    person_count = len(tracked_persons)
    animal_count = len(tracked_animals)
    
    # Nếu không có track IDs, sử dụng class_counts
    if person_count == 0 and 'person' in class_counts:
        person_count = class_counts['person']
    
    total_animal_count = 0
    for animal in animal_classes:
        if animal in class_counts:
            total_animal_count += class_counts[animal]
    
    if animal_count == 0:
        animal_count = total_animal_count
    
    # Tạo kết quả
    results = {
        'frame_count': frame_count,
        'person_count': person_count,
        'animal_count': animal_count,
        'class_counts': class_counts,
        'unique_objects': len(tracked_persons) + len(tracked_animals)
    }
    
    return results

def update_session_detection_counts():
   def update_session_detection_counts():
        """Cập nhật detection counts cho tất cả các sessions"""
        app = create_app()
        
        with app.app_context():
            # Chỉ lấy ra các sessions có output_path, không kiểm tra summary
            sessions = TrackingSession.query.filter(
                TrackingSession.output_path.isnot(None)
            ).all()
            
            # Lọc sessions cần cập nhật bằng Python
            sessions_to_update = []
            for session in sessions:
                try:
                    if not hasattr(session, 'summary') or session.summary is None or not session.summary:
                        sessions_to_update.append(session)
                except:
                    # Nếu có lỗi khi truy cập thuộc tính summary, giả định cần cập nhật
                    sessions_to_update.append(session)
            
            if not sessions_to_update:
                print("No sessions found that need updating.")
                return
            
            print(f"Found {len(sessions_to_update)} sessions to update.")
        
        # Phần còn lại giữ nguyên
        
        for session in sessions_to_update:
            print(f"\nUpdating session {session.id}...")
            
            video_path = session.output_path
            if not os.path.exists(video_path):
                print(f"Video file not found: {video_path}")
                continue
            
            try:
                # Analyze video
                results = count_objects_in_video(video_path, Config.MODEL_PATH)
                
                if results:
                    print(f"Detected {results['person_count']} people and {results['animal_count']} animals.")
                    
                    # Update session
                    session.summary = {
                        'person_count': results['person_count'],
                        'animal_count': results['animal_count'],
                        'total_objects': results['unique_objects'],
                        'class_counts': results['class_counts']
                    }
                    
                    db.session.commit()
                    print(f"Session {session.id} updated successfully.")
            except Exception as e:
                print(f"Error updating session {session.id}: {e}")
                db.session.rollback()
        
        print("\nUpdate completed.")

if __name__ == "__main__":
    update_session_detection_counts()