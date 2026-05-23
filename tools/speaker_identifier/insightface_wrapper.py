import os
import cv2
import numpy as np
import warnings
from pathlib import Path

# Prevent excessive warnings from ONNX Runtime
os.environ["ORT_LOGGING_LEVEL"] = "3"

class InsightFaceAnalysis:
    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu
        self.app = None
        
    def _lazy_init(self):
        if self.app is not None:
            return
        
        # Import inside method to avoid startup delays
        import insightface
        from insightface.app import FaceAnalysis
        
        # Disable warnings
        warnings.filterwarnings("ignore", category=UserWarning)
        
        # Initialize FaceAnalysis with 'buffalo_l' (which downloads models to ~/.insightface/models/)
        ctx_id = 0 if self.use_gpu else -1
        self.app = FaceAnalysis(name='buffalo_l', allowed_modules=['detection', 'recognition', 'genderage'])
        self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))
        
    def analyze_frame(self, frame) -> list[dict]:
        """
        Analyzes a single video frame.
        Returns a list of dicts, each containing:
          - 'bbox': [x1, y1, x2, y2]
          - 'embedding': list of 512 floats
          - 'gender': 'M' or 'F'
          - 'age': estimated age (int)
        """
        self._lazy_init()
        if frame is None:
            return []
            
        faces = self.app.get(frame)
        results = []
        for face in faces:
            results.append({
                "bbox": face.bbox.astype(int).tolist(),
                "embedding": face.normed_embedding.tolist() if face.embedding is not None else [],
                "gender": "M" if face.gender == 1 else "F",
                "age": int(face.age)
            })
        return results

    def extract_crop_embedding(self, frame, bbox) -> dict | None:
        """
        Crops the face using bounding box, runs it through InsightFace to get clean features.
        """
        self._lazy_init()
        if frame is None or len(bbox) != 4:
            return None
            
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        # Add some margin
        padding = int(max(x2 - x1, y2 - y1) * 0.1)
        x1_pad = max(0, x1 - padding)
        y1_pad = max(0, y1 - padding)
        x2_pad = min(w, x2 + padding)
        y2_pad = min(h, y2 + padding)
        
        crop = frame[y1_pad:y2_pad, x1_pad:x2_pad]
        if crop.size == 0:
            return None
            
        # Detect in the cropped region
        faces = self.app.get(crop)
        if not faces:
            # Fallback to the whole frame detector but filtered by IoU
            faces_whole = self.app.get(frame)
            if faces_whole:
                # Find the one that overlaps most with bbox
                best_face = None
                best_iou = 0.0
                for face in faces_whole:
                    iou = self._bbox_iou(face.bbox, bbox)
                    if iou > best_iou:
                        best_iou = iou
                        best_face = face
                if best_face and best_iou > 0.4:
                    return {
                        "embedding": best_face.normed_embedding.tolist() if best_face.embedding is not None else [],
                        "gender": "M" if best_face.gender == 1 else "F",
                        "age": int(best_face.age)
                    }
            return None
            
        # Return the largest face in the crop
        largest_face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
        return {
            "embedding": largest_face.normed_embedding.tolist() if largest_face.embedding is not None else [],
            "gender": "M" if largest_face.gender == 1 else "F",
            "age": int(largest_face.age)
        }
        
    def _bbox_iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        if float(boxAArea + boxBArea - interArea) == 0:
            return 0.0
        return interArea / float(boxAArea + boxBArea - interArea)
