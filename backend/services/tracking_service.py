import os
import time
import threading
from datetime import datetime, timedelta
from models.database import db, TrackingSession, Detection
from utils.tracking_bytetrack import ByteTracker
from config import Config

class TrackingService:
    def __init__(self):
        self.model_path = Config.MODEL_PATH
        self.output_folder = Config.OUTPUT_FOLDER
        self.tracker = ByteTracker(self.model_path, self.output_folder)
        
        # Make sure output directory exists
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Tracking status
        self.active_trackings = {}
    
    def process_video(self, video_path, session_id=None):
        """Process a video file and track objects"""
        # Create a new tracking session if not provided
        if not session_id:
            filename = os.path.basename(video_path)
            session = TrackingSession(
                source_type='video',
                filename=filename,
                start_time=datetime.utcnow()
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id
        
        # Define output filename
        output_filename = f"tracked_video_{session_id}.mp4"
        output_path = os.path.join(self.output_folder, output_filename)
        
        # Start tracking in a new thread
        tracking_thread = threading.Thread(
            target=self._process_video_thread,
            args=(video_path, output_filename, session_id)
        )
        
        self.active_trackings[session_id] = {
            'thread': tracking_thread,
            'status': 'starting',
            'progress': 0
        }
        
        tracking_thread.start()
        
        return {
            'session_id': session_id,
            'status': 'processing',
            'message': 'Video processing started'
        }
    
    def _process_video_thread(self, video_path, output_filename, session_id):
        """Thread function to process video"""
        try:
            self.active_trackings[session_id]['status'] = 'processing'
            
            # Process the video
            results = self.tracker.process_video(video_path, output_filename)
            
            # Update the session
            session = TrackingSession.query.get(session_id)
            if session:
                session.end_time = datetime.utcnow()
                session.duration = (session.end_time - session.start_time).total_seconds()
                session.output_path = results['output_path']
                db.session.commit()
            
            # Record detections
            frame_data = results.get('frame_data', [])
            detections_to_add = []
            
            # Group by 30 frames (approximately 1 second at 30fps) to reduce DB entries
            for i in range(0, len(frame_data), 30):
                chunk = frame_data[i:i+30]
                if not chunk:
                    continue
                
                # Get average for this second
                avg_frame = {
                    'frame_number': chunk[0]['frame_number'],
                    'person_count': sum(frame['person_count'] for frame in chunk) // len(chunk),
                    'animal_count': sum(frame['animal_count'] for frame in chunk) // len(chunk)
                }
                
                # Add person detection
                if avg_frame['person_count'] > 0:
                    detections_to_add.append(
                        Detection(
                            session_id=session_id,
                            timestamp=session.start_time + timedelta(seconds=i//30),
                            class_name='person',
                            count=avg_frame['person_count'],
                            frame_number=avg_frame['frame_number']
                        )
                    )
                
                # Add animal detection
                if avg_frame['animal_count'] > 0:
                    detections_to_add.append(
                        Detection(
                            session_id=session_id,
                            timestamp=session.start_time + timedelta(seconds=i//30),
                            class_name='animal',
                            count=avg_frame['animal_count'],
                            frame_number=avg_frame['frame_number']
                        )
                    )
            
            # Bulk insert detections
            if detections_to_add:
                db.session.bulk_save_objects(detections_to_add)
                db.session.commit()
                
            self.active_trackings[session_id]['status'] = 'completed'
            self.active_trackings[session_id]['progress'] = 100
            
        except Exception as e:
            self.active_trackings[session_id]['status'] = 'error'
            self.active_trackings[session_id]['error'] = str(e)
            print(f"Error processing video: {e}")
    
    def start_camera_tracking(self, camera_id=0):
        """Start tracking from camera feed"""
        # Create a new tracking session
        session = TrackingSession(
            source_type='camera',
            start_time=datetime.utcnow()
        )
        db.session.add(session)
        db.session.commit()
        session_id = session.id
        
        # Define output filename
        output_filename = f"camera_tracking_{session_id}.mp4"
        
        # Start tracking in a new thread
        tracking_thread = threading.Thread(
            target=self._camera_tracking_thread,
            args=(camera_id, output_filename, session_id)
        )
        
        self.active_trackings[session_id] = {
            'thread': tracking_thread,
            'status': 'starting',
            'progress': 0
        }
        
        tracking_thread.start()
        
        return {
            'session_id': session_id,
            'status': 'processing',
            'message': 'Camera tracking started'
        }
    
    def _camera_tracking_thread(self, camera_id, output_filename, session_id):
        """Thread function to process camera feed"""
        try:
            self.active_trackings[session_id]['status'] = 'processing'
            
            # Start camera tracking
            results = self.tracker.start_camera_tracking(camera_id, output_filename)
            
            # Update the session
            session = TrackingSession.query.get(session_id)
            if session:
                session.end_time = datetime.utcnow()
                session.duration = results['duration']
                session.output_path = results['output_path']
                db.session.commit()
            
            # Record detections
            frame_data = results.get('frame_data', [])
            detections_to_add = []
            
            # Group by 30 frames (approximately 1 second at 30fps) to reduce DB entries
            for i in range(0, len(frame_data), 30):
                chunk = frame_data[i:i+30]
                if not chunk:
                    continue
                
                # Get average for this second
                avg_frame = {
                    'frame_number': chunk[0]['frame_number'],
                    'person_count': sum(frame['person_count'] for frame in chunk) // len(chunk),
                    'animal_count': sum(frame['animal_count'] for frame in chunk) // len(chunk)
                }
                
                # Add person detection
                if avg_frame['person_count'] > 0:
                    detections_to_add.append(
                        Detection(
                            session_id=session_id,
                            timestamp=session.start_time + timedelta(seconds=i//30),
                            class_name='person',
                            count=avg_frame['person_count'],
                            frame_number=avg_frame['frame_number']
                        )
                    )
                
                # Add animal detection
                if avg_frame['animal_count'] > 0:
                    detections_to_add.append(
                        Detection(
                            session_id=session_id,
                            timestamp=session.start_time + timedelta(seconds=i//30),
                            class_name='animal',
                            count=avg_frame['animal_count'],
                            frame_number=avg_frame['frame_number']
                        )
                    )
            
            # Bulk insert detections
            if detections_to_add:
                db.session.bulk_save_objects(detections_to_add)
                db.session.commit()
                
            self.active_trackings[session_id]['status'] = 'completed'
            self.active_trackings[session_id]['progress'] = 100
            
        except Exception as e:
            self.active_trackings[session_id]['status'] = 'error'
            self.active_trackings[session_id]['error'] = str(e)
            print(f"Error in camera tracking: {e}")
    
    def stop_camera_tracking(self, session_id):
        """Stop an active camera tracking session"""
        if session_id in self.active_trackings:
            # Set a flag to stop tracking
            self.active_trackings[session_id]['status'] = 'stopping'
            return {'status': 'stopping', 'message': 'Stopping camera tracking'}
        else:
            return {'status': 'error', 'message': 'No active tracking session found'}
    
    def get_tracking_status(self, session_id):
        """Get status of a tracking session"""
        if session_id in self.active_trackings:
            return {
                'session_id': session_id,
                'status': self.active_trackings[session_id]['status'],
                'progress': self.active_trackings[session_id]['progress'],
                'error': self.active_trackings[session_id].get('error')
            }
        else:
            # Check database for completed sessions
            session = TrackingSession.query.get(session_id)
            if session:
                status = 'completed' if session.end_time else 'unknown'
                return {
                    'session_id': session_id,
                    'status': status,
                    'progress': 100 if status == 'completed' else 0
                }
            else:
                return {'status': 'error', 'message': 'Session not found'}
    
    def get_session_details(self, session_id):
        """Get detailed information about a tracking session"""
        session = TrackingSession.query.get(session_id)
        if not session:
            return None
        
        return session.to_dict()
    
    def get_all_sessions(self):
        """Get all tracking sessions"""
        sessions = TrackingSession.query.order_by(TrackingSession.start_time.desc()).all()
        return [session.to_dict() for session in sessions]
    # Cập nhật services/tracking_service.py - phương thức _process_video_thread
def _process_video_thread(self, video_path, output_filename, session_id):
    """Thread function to process video"""
    try:
        self.active_trackings[session_id]['status'] = 'processing'
        
        # Process the video
        results = self.tracker.process_video(video_path, output_filename)
        
        # Update the session
        session = TrackingSession.query.get(session_id)
        if session:
            session.end_time = datetime.utcnow()
            session.duration = (session.end_time - session.start_time).total_seconds()
            session.output_path = results['output_path']
            
            # Add summary data to session
            if not hasattr(session, 'summary'):
                session.summary = {}
            
            session.summary = {
                'person_count': results.get('person_count', 0),
                'animal_count': results.get('animal_count', 0),
                'total_objects': results.get('unique_objects', 0),
                'class_counts': results.get('class_counts', {})
            }
            
            db.session.commit()
        
        # Record detections
        frame_data = results.get('frame_data', [])
        detections_to_add = []
        
        # Group by 30 frames (approximately 1 second at 30fps) to reduce DB entries
        for i in range(0, len(frame_data), 30):
            chunk = frame_data[i:i+30]
            if not chunk:
                continue
            
            # Get average for this second
            avg_frame = {
                'frame_number': chunk[0]['frame_number'],
                'person_count': sum(frame['person_count'] for frame in chunk) // len(chunk),
                'animal_count': sum(frame['animal_count'] for frame in chunk) // len(chunk)
            }
            
            # Add person detection
            if avg_frame['person_count'] > 0:
                detections_to_add.append(
                    Detection(
                        session_id=session_id,
                        timestamp=session.start_time + timedelta(seconds=i//30),
                        class_name='person',
                        count=avg_frame['person_count'],
                        frame_number=avg_frame['frame_number']
                    )
                )
            
            # Add animal detection
            if avg_frame['animal_count'] > 0:
                detections_to_add.append(
                    Detection(
                        session_id=session_id,
                        timestamp=session.start_time + timedelta(seconds=i//30),
                        class_name='animal',
                        count=avg_frame['animal_count'],
                        frame_number=avg_frame['frame_number']
                    )
                )
        
        # Bulk insert detections
        if detections_to_add:
            db.session.bulk_save_objects(detections_to_add)
            db.session.commit()
            
        self.active_trackings[session_id]['status'] = 'completed'
        self.active_trackings[session_id]['progress'] = 100
        
    except Exception as e:
        self.active_trackings[session_id]['status'] = 'error'
        self.active_trackings[session_id]['error'] = str(e)
        print(f"Error processing video: {e}")