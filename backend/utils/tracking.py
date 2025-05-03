import cv2
import numpy as np
import torch
import time
import os
from ultralytics import YOLO
from deep_sort_pytorch.utils.parser import get_config
from deep_sort_pytorch.deep_sort import DeepSort

class ObjectTracker:
    def __init__(self, model_path, config_path, output_folder):
        # Initialize YOLO model
        self.model = YOLO(model_path)
        
        # Initialize DeepSORT
        cfg = get_config()
        cfg.merge_from_file(config_path)
        self.deepsort = DeepSort(
            cfg.DEEPSORT.REID_CKPT,
            max_dist=cfg.DEEPSORT.MAX_DIST,
            min_confidence=cfg.DEEPSORT.MIN_CONFIDENCE,
            nms_max_overlap=cfg.DEEPSORT.NMS_MAX_OVERLAP,
            max_iou_distance=cfg.DEEPSORT.MAX_IOU_DISTANCE,
            max_age=cfg.DEEPSORT.MAX_AGE,
            n_init=cfg.DEEPSORT.N_INIT,
            nn_budget=cfg.DEEPSORT.NN_BUDGET,
            use_cuda=True
        )
        
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)
        
        # Class names from COCO dataset
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
        # Get detections from YOLO
        results = self.model(frame, verbose=False)
        result = results[0]
        
        # Extract bounding boxes, confidence scores and class IDs
        boxes = []
        confidences = []
        class_ids = []
        
        for det in result.boxes:
            x1, y1, x2, y2 = det.xyxy[0].tolist()
            conf = det.conf[0].item()
            cls_id = int(det.cls[0].item())
            
            boxes.append([x1, y1, x2, y2])
            confidences.append(conf)
            class_ids.append(cls_id)
        
        # Update frame metrics
        self.metrics['total_frames'] += 1
        self.metrics['total_detections'] += len(boxes)
        
        # Convert format for DeepSORT
        if boxes:
            xywhs = []
            confs = []
            clss = []
            
            for (x1, y1, x2, y2), conf, cls_id in zip(boxes, confidences, class_ids):
                w, h = x2 - x1, y2 - y1
                xywhs.append([x1 + w/2, y1 + h/2, w, h])
                confs.append(conf)
                clss.append(cls_id)
                
                # Update class counts
                class_name = self.class_names[cls_id]
                if class_name not in self.metrics['class_counts']:
                    self.metrics['class_counts'][class_name] = 0
                self.metrics['class_counts'][class_name] += 1
                
                # Track specific categories
                if class_name == 'person':
                    self.metrics['person_count'] += 1
                elif class_name in self.animal_classes:
                    self.metrics['animal_count'] += 1
            
            xywhs = torch.Tensor(xywhs)
            confs = torch.Tensor(confs)
            clss = torch.Tensor(clss)
            
            # Run DeepSORT
            outputs = self.deepsort.update(xywhs.cpu(), confs.cpu(), clss.cpu(), frame)
            
            # Draw boxes for tracked objects
            if len(outputs) > 0:
                for output in outputs:
                    x1, y1, x2, y2, track_id, cls_id = output
                    class_name = self.class_names[int(cls_id)]
                    
                    # Add to tracked objects set
                    track_key = f"{class_name}_{track_id}"
                    self.metrics['tracked_objects'].add(track_key)
                    
                    # Draw bounding box
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    
                    # Draw label
                    label = f"{class_name} #{track_id}"
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
                frame_data.append({
                    'frame_number': frame_idx,
                    'detections': sum(1 for obj in self.metrics['tracked_objects'] if f"_{frame_idx}_" in obj),
                    'person_count': sum(1 for obj in self.metrics['tracked_objects'] if obj.startswith('person_')),
                    'animal_count': sum(1 for obj in self.metrics['tracked_objects'] if any(obj.startswith(animal + '_') for animal in self.animal_classes))
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
                frame_data.append({
                    'frame_number': frame_idx,
                    'timestamp': time.time() - start_time,
                    'detections': self.metrics['total_detections'],
                    'person_count': sum(1 for obj in self.metrics['tracked_objects'] if obj.startswith('person_')),
                    'animal_count': sum(1 for obj in self.metrics['tracked_objects'] if any(obj.startswith(animal + '_') for animal in self.animal_classes))
                })
                
                frame_idx += 1
                
                # Display progress
                if frame_idx % 30 == 0:  # Update every second (assuming 30 fps)
                    elapsed_time = time.time() - start_time
                    print(f"Recording: {int(elapsed_time)}s, Frames: {frame_idx}")
                
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