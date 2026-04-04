class SimpleTracker:
    """Simple IoU-based tracker for object tracking."""
    def __init__(self, max_age=30, iou_threshold=0.3):
        self.max_age = max_age
        self.iou_threshold = iou_threshold
        self.tracks = {}
        self.next_id = 1
        self.track_ages = {}
    
    def update(self, detections):
        """Update tracks with new detections."""
        results = []
        matched = set()
        
        for det in detections:
            best_iou = 0
            best_track_id = None
            det_box = det['bbox']
            det_label = det['label']
            
            for track_id, track in self.tracks.items():
                if track['label'] != det_label:
                    continue
                iou = self._calc_iou(det_box, track['bbox'])
                if iou > best_iou and iou > self.iou_threshold:
                    best_iou = iou
                    best_track_id = track_id
            
            if best_track_id is not None:
                self.tracks[best_track_id]['bbox'] = det_box
                self.tracks[best_track_id]['confidence'] = det['confidence']
                self.track_ages[best_track_id] = 0
                matched.add(best_track_id)
                results.append({**det, 'track_id': best_track_id})
            else:
                track_id = self.next_id
                self.next_id += 1
                self.tracks[track_id] = {
                    'bbox': det_box,
                    'label': det_label,
                    'confidence': det['confidence']
                }
                self.track_ages[track_id] = 0
                matched.add(track_id)
                results.append({**det, 'track_id': track_id})
        
        to_remove = []
        for track_id in self.tracks:
            if track_id not in matched:
                self.track_ages[track_id] += 1
                if self.track_ages[track_id] > self.max_age:
                    to_remove.append(track_id)
        
        for track_id in to_remove:
            del self.tracks[track_id]
            del self.track_ages[track_id]
        
        return results
    
    def _calc_iou(self, box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - inter
        
        return inter / union if union > 0 else 0
