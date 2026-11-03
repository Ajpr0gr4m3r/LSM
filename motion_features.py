"""Ordered fingertip trajectories; all coordinates preserve handedness/direction."""
import numpy as np


def tracks(points):
    from recognition_features import regions, normalize_sequence, smooth_landmarks
    raw = np.asarray(points, np.float32)
    body = normalize_sequence(smooth_landmarks(raw))
    output, visible = [], []
    for original, hand in zip(regions(raw)[-2:], regions(body)[-2:]):
        present = np.any(original != 0, axis=(1, 2))
        output.append(hand[:, [0, 4, 8, 12, 16, 20], :2])
        visible.append(present)
    return np.concatenate(output, axis=1), np.stack(visible, axis=1)


def trajectory_descriptor(points):
    """16 ordered samples of wrist + ALL tips, displacement and signed velocity.

    Translate each track relative to its first visible point. Never rotate,
    reflect or reverse the path. Missing frames are masked, not motion jumps.
    """
    paths, visible = tracks(points)
    descriptors = []
    for h in range(2):
        present = visible[:, h]
        path = paths[:, h*6:(h+1)*6]
        if np.count_nonzero(present) < .8 * len(path):
            descriptors.append(np.zeros(16*24 + 6 + 1, np.float32))
            continue
        valid = np.flatnonzero(present)
        flattened = path.reshape(len(path), 12)
        filled = np.stack([np.interp(np.arange(len(path)), valid, flattened[valid, i]) for i in range(12)], axis=1)
        sample = np.stack([np.interp(np.linspace(0, len(path)-1, 16), np.arange(len(path)), filled[:, i]) for i in range(12)], axis=1)
        delta = np.diff(sample, axis=0, prepend=sample[:1])
        displacement = sample - sample[:1]
        length = np.linalg.norm(delta.reshape(16, 6, 2), axis=-1).sum(axis=0)
        descriptors.append(np.r_[displacement.ravel(), delta.ravel()*4, length, present.mean()])
    return np.concatenate(descriptors).astype(np.float32)


def motion_summary(points):
    paths, visible = tracks(points)
    speeds, extents = [], []
    for h in range(2):
        valid = visible[1:, h] & visible[:-1, h]
        path = paths[:, h*6:(h+1)*6]
        delta = np.linalg.norm(np.diff(path, axis=0), axis=-1)
        if visible[:, h].mean() < .8: continue
        extent = np.linalg.norm(np.ptp(path[visible[:, h]], axis=0), axis=-1)
        extents.append(float(np.max(extent)))
        tail = delta[-4:][valid[-4:]]
        if len(tail) == 4: speeds.append(float(np.max(np.mean(tail, axis=0))))
    return {'extent': max(extents, default=0.), 'tail_speed': max(speeds, default=0.)}


def fit_motion_profile(points, targets):
    """Learn which classes move; no label names or letter-specific rules."""
    summaries = [motion_summary(p) for p in points]
    extent = np.array([r['extent'] for r in summaries])
    tails = np.array([r['tail_speed'] for r in summaries])
    medians = [float(np.median(extent[targets == i])) for i in sorted(np.unique(targets))]
    baseline = max(.04, float(np.quantile(medians, .2)))
    moving = [i for i, value in enumerate(medians) if value > max(.12, 2.5*baseline)]
    quiet = tails[tails <= np.quantile(tails, .4)]
    threshold = max(.02, float(np.median(quiet))*3)
    return {'version': 'trajectory-profile-v1', 'moving_classes': moving,
            'tail_speed_reference': threshold, 'class_extent_medians': medians,
            'note': 'Movimiento aprendido solo con entrenamiento; una postura inicial no permite anticipar un movimiento futuro.'}


def augment_timing(points, targets):
    """Ordered time warps preserve direction and endpoints, including a brief
    final hold. No reversal or mirroring and no additional training volume
    compared with the existing three-way augmentation.
    """
    from recognition_features import regions
    outputs=[points.copy()]
    for exponent,hold in ((.8,0),(1.2,4)):
        varied=np.empty_like(points)
        for i,sequence in enumerate(points):
            count=len(sequence)-hold
            positions=(np.linspace(0,1,count)**exponent)*(len(sequence)-1)
            if hold:positions=np.r_[positions,np.repeat(len(sequence)-1,hold)]
            low=np.floor(positions).astype(int);high=np.ceil(positions).astype(int)
            alpha=(positions-low)[:,None]
            varied[i]=sequence[low]*(1-alpha)+sequence[high]*alpha
            for original,region in zip(regions(sequence),regions(varied[i])):
                present=np.any(original[...,:3]!=0,axis=-1)
                valid=present[low]&present[high]
                region[...,:3]=np.where(valid[...,None],region[...,:3],0)
        outputs.append(varied)
    return np.concatenate(outputs),np.concatenate([targets]*3)


def motion_challenges(points, targets, profile, guard, labels):
    """Synthetic trajectory checks on held-out recordings, not unknown-sign FAR.
    The candidate class is deliberately fixed, so this does not measure the
    complete classifier. Results never choose checkpoints or decision limits.
    """
    from recognition_features import temporal_guard_accept
    rows=[]
    for i in profile['moving_classes']:
        selected=points[targets==i]
        counts={'original_accepted':0,'static_rejected':0,'reversed_rejected':0,'partial_rejected':0}
        for p in selected:
            frozen=np.repeat(p[:1],len(p),axis=0)
            partial=np.concatenate([p[:len(p)//2],np.repeat(p[len(p)//2-1:len(p)//2],len(p)-len(p)//2,axis=0)])
            counts['original_accepted']+=int(temporal_guard_accept(p,i,guard))
            counts['static_rejected']+=int(not temporal_guard_accept(frozen,i,guard))
            counts['reversed_rejected']+=int(not temporal_guard_accept(p[::-1],i,guard))
            counts['partial_rejected']+=int(not temporal_guard_accept(partial,i,guard))
        rows.append({**labels[i],'evaluated':len(selected),**counts})
    return {'by_class':rows,'note':'Variantes sintéticas con clase fijada: diagnóstico del filtro temporal, no precisión del clasificador ni tasa de falsos positivos reales.'}
