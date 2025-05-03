import cv2
import numpy as np
import torch
import time
import os
from ultralytics import YOLO

class ByteTracker:
    def __init__(self, model_path, output_folder):
        # Initialize YOLO model
        self.model = YOLO(model_path)
        
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)
        
        # Class names from model
        self.class_names = self.model.names
        
        # Track metrics
        self.reset_metrics()
    
    def reset_metrics(self):
        self.metrics = {
            'total_frames': 0,
            'total_detections': 0,
            'class_counts': {},
            'tracked_objects': set(),
            'person_count': 0,
            'animal_count': 0
        }
        
        # Animals in COCO dataset
        self.animal_classes = {'dog', 'cat', 'bird', 'horse', 'sheep', 'cow', 
                               'elephant', 'bear', 'zebra', 'giraffe'}
    
    def process_frame(self, frame, frame_idx):
        # Get detections from YOLO with tracking enabled
        results = self.model.track(frame, persist=True, verbose=False)
        
        # Update frame metrics
        self.metrics['total_frames'] += 1
        
        # Extract results
        if results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id
            if track_ids is not None:
                track_ids = track_ids.int().cpu().numpy()
            else:
                track_ids = [None] * len(boxes)
                
            cls_ids = results[0].boxes.cls.int().cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()
            
            for box, track_id, cls_id, conf in zip(boxes, track_ids, cls_ids, confs):
                x1, y1, x2, y2 = box
                class_name = self.class_names[cls_id]
                
                # Update class counts
                if class_name not in self.metrics['class_counts']:
                    self.metrics['class_counts'][class_name] = 0
                self.metrics['class_counts'][class_name] += 1
                
                # Track specific categories
                if track_id is not None:
                    track_key = f"{class_name}_{track_id}"
                    self.metrics['tracked_objects'].add(track_key)
                    
                    if class_name == 'person':
                        self.metrics['person_count'] += 1
                    elif class_name in self.animal_classes:
                        self.metrics['animal_count'] += 1
                
                # Draw bounding box
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                
                # Draw label with track ID if available
                if track_id is not None:
                    label = f"{class_name} #{track_id} {conf:.2f}"
                else:
                    label = f"{class_name} {conf:.2f}"
                    
                t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
                cv2.rectangle(frame, (int(x1), int(y1)-t_size[1]-10), (int(x1)+t_size[0], int(y1)), (0, 255, 0), -1)
                cv2.putText(frame, label, (int(x1), int(y1)-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, [255, 255, 255], 1)
        
        # Add frame count and timestamp
        cv2.putText(frame, f"Frame: {frame_idx}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Add total count
        person_count = len([obj for obj in self.metrics['tracked_objects'] if obj.startswith('person_')])
        animal_count = len([obj for obj in self.metrics['tracked_objects'] if any(obj.startswith(animal + '_') for animal in self.animal_classes)])
        
        cv2.putText(frame, f"People: {person_count}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.putText(frame, f"Animals: {animal_count}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        return frame
    
    def process_video(self, video_path, output_filename=None):
        # Open video file
        cap = cv2.VideoCapture(video_path)
        
        # Get video properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Reset metrics
        self.reset_metrics()
        
        # Prepare output
        if output_filename is None:
            video_name = os.path.basename(video_path)
            output_filename = f"tracked_{video_name}"
        
        output_path = os.path.join(self.output_folder, output_filename)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # Process video
        frame_idx = 0
        frame_data = []
        
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Process current frame
                processed_frame = self.process_frame(frame, frame_idx)
                
                # Write to output
                out.write(processed_frame)
                
                # Save detection data for this frame
                person_count = len([obj for obj in self.metrics['tracked_objects'] if obj.startswith('person_')])
                animal_count = len([obj for obj in self.metrics['tracked_objects'] if any(obj.startswith(animal + '_') for animal in self.animal_classes)])
                
                frame_data.append({
                    'frame_number': frame_idx,
                    'person_count': person_count,
                    'animal_count': animal_count
                })
                
                frame_idx += 1
                
                # Print progress
                if frame_idx % 100 == 0:
                    progress = (frame_idx / total_frames) * 100
                    print(f"Processing: {progress:.2f}% complete")
        
        finally:
            # Release resources
            cap.release()
            out.release()
        
        # Calculate final metrics
        unique_person_count = len([obj for obj in self.metrics['tracked_objects'] if obj.startswith('person_')])
        unique_animal_count = len([obj for obj in self.metrics['tracked_objects'] if any(obj.startswith(animal + '_') for animal in self.animal_classes)])
        
        results = {
            'output_path': output_path,
            'total_frames': frame_idx,
            'unique_objects': len(self.metrics['tracked_objects']),
            'person_count': unique_person_count,
            'animal_count': unique_animal_count,
            'class_counts': self.metrics['class_counts'],
            'frame_data': frame_data
        }
        
        return results
    
    def start_camera_tracking(self, camera_id=0, output_filename=None):
        # Reset metrics
        self.reset_metrics()
        
        # Open camera
        cap = cv2.VideoCapture(camera_id)
        
        # Get video properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = 30  # Assumed for camera
        
        # Prepare output
        if output_filename is None:
            timestamp = int(time.time())
            output_filename = f"camera_tracking_{timestamp}.mp4"
        
        output_path = os.path.join(self.output_folder, output_filename)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # Process camera feed
        frame_idx = 0
        frame_data = []
        start_time = time.time()
        
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Process current frame
                processed_frame = self.process_frame(frame, frame_idx)
                
                # Write to output
                out.write(processed_frame)
                
                # Save detection data for this frame
                person_count = len([obj for obj in self.metrics['tracked_objects'] if obj.startswith('person_')])
                animal_count = len([obj for obj in self.metrics['tracked_objects'] if any(obj.startswith(animal + '_') for animal in self.animal_classes)])
                
                frame_data.append({
                    'frame_number': frame_idx,
                    'timestamp': time.time() - start_time,
                    'person_count': person_count,
                    'animal_count': animal_count
                })
                
                frame_idx += 1
                
                # Display progress
                if frame_idx % 30 == 0:  # Update every second (assuming 30 fps)
                    elapsed_time = time.time() - start_time
                    print(f"Recording: {int(elapsed_time)}s, Frames: {frame_idx}")
                
                # Display the resulting frame
                cv2.imshow('Camera Tracking', processed_frame)
                
                # Break if user presses 'q'
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        finally:
            # Release resources
            cap.release()
            out.release()
            cv2.destroyAllWindows()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate final metrics
        unique_person_count = len([obj for obj in self.metrics['tracked_objects'] if obj.startswith('person_')])
        unique_animal_count = len([obj for obj in self.metrics['tracked_objects'] if any(obj.startswith(animal + '_') for animal in self.animal_classes)])
        
        results = {
            'output_path': output_path,
            'total_frames': frame_idx,
            'duration': duration,
            'unique_objects': len(self.metrics['tracked_objects']),
            'person_count': unique_person_count,
            'animal_count': unique_animal_count,
            'class_counts': self.metrics['class_counts'],
            'frame_data': frame_data
        }
        
        return results