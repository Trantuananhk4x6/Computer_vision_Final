from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# Cập nhật models/database.py - class TrackingSession
class TrackingSession(db.Model):
    __tablename__ = 'tracking_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    source_type = db.Column(db.String(50))  # 'video', 'camera', etc.
    filename = db.Column(db.String(255), nullable=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.Float, nullable=True)  # in seconds
    output_path = db.Column(db.String(255), nullable=True)
    summary = db.Column(db.JSON, nullable=True)  # Store detection stats here
    
    detections = db.relationship('Detection', backref='session', lazy=True, 
                                cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'source_type': self.source_type,
            'filename': self.filename,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'output_path': self.output_path,
            'summary': self.summary or {}
        }

class Detection(db.Model):
    __tablename__ = 'detections'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('tracking_sessions.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    class_name = db.Column(db.String(50), nullable=False)
    count = db.Column(db.Integer, default=0)
    confidence = db.Column(db.Float)  # Average confidence for this class
    frame_number = db.Column(db.Integer)
    
    def __repr__(self):
        return f'<Detection {self.id} - {self.class_name}: {self.count}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat(),
            'class_name': self.class_name,
            'count': self.count,
            'confidence': self.confidence,
            'frame_number': self.frame_number
        }