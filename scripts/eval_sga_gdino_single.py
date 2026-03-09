#!/usr/bin/env python3
"""Evaluate SGA with GroundingDINO detections - single video (OPTIMIZED)."""

import sys
import pickle
import torch
import cv2
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from orion.sga.ag_dataset_v2 import AG_OBJECT_CLASSES, AG_ALL_PREDICATES
from orion.sga.temporal_model import TemporalSGAConfig, TemporalSGAModel
from orion.perception.detectors.grounding_dino import GroundingDINOWrapper

OBJECT_TO_IDX = {c: i for i, c in enumerate(AG_OBJECT_CLASSES)}
PREDICATE_TO_IDX = {p: i for i, p in enumerate(AG_ALL_PREDICATES)}
IDX_TO_PREDICATE = {i: p for i, p in enumerate(AG_ALL_PREDICATES)}

# Better label normalization for GroundingDINO outputs
LABEL_ALIASES = {
    'sofa': 'sofa/couch', 'couch': 'sofa/couch',
    'cabinet': 'closet/cabinet', 'closet': 'closet/cabinet',
    'cup': 'cup/glass/bottle', 'glass': 'cup/glass/bottle', 'bottle': 'cup/glass/bottle',
    'phone': 'phone/camera', 'camera': 'phone/camera', 'cellphone': 'phone/camera',
    'paper': 'paper/notebook', 'notebook': 'paper/notebook',
    'tv': 'television', 'monitor': 'television',
}

def main():
    vid = sys.argv[1] if len(sys.argv) > 1 else '001YG'
    
    # Determine device
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}")
    
    # Load AG annotations
    print("Loading AG annotations...")
    possible_anno_paths = [
        'datasets/ActionGenome/annotations/action_genome_v1.0/object_bbox_and_relationship.pkl',
        'datasets/ActionGenome/object_bbox_and_relationship.pkl',
        '../datasets/ActionGenome/object_bbox_and_relationship.pkl',
        '../datasets/ActionGenome/annotations/action_genome_v1.0/object_bbox_and_relationship.pkl'
    ]
    
    anno_path = next((p for p in possible_anno_paths if Path(p).exists()), None)
    if not anno_path:
        print(f"Error: Could not find object_bbox_and_relationship.pkl. Checked: {possible_anno_paths}")
        return

    with open(anno_path, 'rb') as f:
        ag = pickle.load(f)
    
    # Build AG prompt for GroundingDINO
    ag_prompt = '. '.join(AG_OBJECT_CLASSES)
    print(f"AG prompt: {ag_prompt[:100]}...")
    
    # Load GroundingDINO
    print("Loading GroundingDINO...")
    gdino = GroundingDINOWrapper(device=device, use_half_precision=False)
    
    # Load SGA model
    print("Loading SGA model...")
    ckpt = torch.load('models/temporal_sga_best.pt', map_location='cpu', weights_only=False)
    cfg = ckpt.get('config', TemporalSGAConfig())
    if isinstance(cfg, dict):
        cfg = TemporalSGAConfig(**cfg)
    model = TemporalSGAModel(cfg)
    model.load_state_dict(ckpt['state_dict'])
    model.to(device).eval()
    print("Models loaded!")
    
    # Get GT frames for this video
    gt_frames = {}
    for k, objs in ag.items():
        if not k.startswith(f'{vid}.mp4/'):
            continue
        fnum = int(k.split('/')[-1].replace('.png', ''))
        triplets = []
        for obj in objs:
            oidx = OBJECT_TO_IDX.get(obj.get('class', ''), -1)
            if oidx < 0:
                continue
            for p in (obj.get('spatial_relationship') or []) + (obj.get('contacting_relationship') or []):
                pidx = PREDICATE_TO_IDX.get(p, -1)
                if pidx >= 0:
                    triplets.append((0, pidx, oidx))
        if triplets:
            gt_frames[fnum] = triplets
    
    print(f"Video {vid}: {len(gt_frames)} GT frames")
    
    # Run GroundingDINO detection
    possible_video_paths = [
        f'datasets/ActionGenome/videos/Charades_v1_480/{vid}.mp4',
        f'datasets/ActionGenome/videos/{vid}.mp4',
        f'../datasets/ActionGenome/videos/{vid}.mp4',
        f'../datasets/ActionGenome/videos/Charades_v1_480/{vid}.mp4'
    ]
    
    vpath = next((Path(p) for p in possible_video_paths if Path(p).exists()), None)
    if not vpath:
        print(f"Video not found: {vid}. Checked: {possible_video_paths}")
        return
    
    print("Running GroundingDINO detection...")
    cap = cv2.VideoCapture(str(vpath))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    dets = defaultdict(list)
    fid = 0
    
    # OPTIMIZATION: Process entire video, lower thresholds
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if fid % 5 == 0:
            # Lower thresholds for more detections
            results = gdino.detect(frame, ag_prompt, box_threshold=0.20, text_threshold=0.15, max_detections=50)
            for det in results:
                label = det['label'].lower().strip()
                # Apply aliases
                label = LABEL_ALIASES.get(label, label)
                if label in OBJECT_TO_IDX:
                    dets[fid].append({
                        'label': label,
                        'bbox': det['bbox'],
                        'conf': det['confidence']
                    })
            if fid % 100 == 0:
                print(f"  Frame {fid}/{total_frames}: {len(dets[fid])} detections")
        fid += 1
    cap.release()
    
    det_frames = sorted(dets.keys())
    print(f"Detection done: {len(det_frames)} frames, {sum(len(d) for d in dets.values())} total detections")
    
    # Evaluate SGA
    r10s, r20s, r50s = [], [], []
    
    for gt_f, gt_triplets in sorted(gt_frames.items()):
        if not det_frames:
            continue
        nearest = min(det_frames, key=lambda x: abs(x - gt_f))
        if abs(nearest - gt_f) > 10:
            continue
        
        idx = det_frames.index(nearest)
        if idx < 8:
            continue
        
        obs_frames = det_frames[idx-8:idx]
        
        # Build tensors
        T, N = 8, 20
        labels = torch.zeros(T, N, dtype=torch.long)
        boxes = torch.zeros(T, N, 4)
        masks = torch.zeros(T, N, dtype=torch.bool)
        
        for t, f in enumerate(obs_frames):
            for i, d in enumerate(dets[f][:N]):
                labels[t, i] = OBJECT_TO_IDX[d['label']]
                b = d['bbox']
                # Use actual video dimensions
                boxes[t, i] = torch.tensor([b[0]/w, b[1]/h, (b[2]-b[0])/w, (b[3]-b[1])/h])
                masks[t, i] = True
        
        if not masks.any():
            continue
        
        # Run model
        with torch.no_grad():
            out = model(
                labels.unsqueeze(0).to(device), 
                boxes.unsqueeze(0).to(device), 
                None, 
                masks.unsqueeze(0).to(device), 
                None, 
                num_future_frames=1
            )
        
        pred_probs = torch.sigmoid(out['predicate_logits'][0, 0])
        
        # Extract predictions - OPTIMIZATION: lower threshold
        preds = []
        valid = masks[-1].nonzero().squeeze(-1).tolist()
        if not isinstance(valid, list):
            valid = [valid]
        
        for oi in range(min(len(valid), pred_probs.shape[0])):
            obj_cls = int(labels[-1, valid[oi]].item())
            for pi in range(pred_probs.shape[1]):
                score = pred_probs[oi, pi].item()
                if score > 0.05:  # Lower threshold for more predictions
                    preds.append((0, pi, obj_cls, score))
        
        preds.sort(key=lambda x: -x[3])
        gt_set = set(gt_triplets)
        
        for k, lst in [(10, r10s), (20, r20s), (50, r50s)]:
            top_k = set((p[0], p[1], p[2]) for p in preds[:k])
            recall = len(top_k & gt_set) / len(gt_set)
            lst.append(recall)
        
        print(f"  Frame {gt_f}: R@20={r20s[-1]:.1%}")
    
    if r20s:
        print(f"\n=== {vid} Results ===")
        print(f"R@10: {sum(r10s)/len(r10s):.2%}")
        print(f"R@20: {sum(r20s)/len(r20s):.2%}")
        print(f"R@50: {sum(r50s)/len(r50s):.2%}")
        print(f"Samples: {len(r20s)}")
    else:
        print("No valid samples")

if __name__ == '__main__':
    main()
