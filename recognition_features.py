"""Preprocesamiento compartido por entrenamiento e inferencia de modelos web v2."""
import numpy as np
from config import FEATURE_DIM, POSE_DIM, FACE_KEY_DIM, FACE_FULL_DIM, USE_FULL_FACE

PREPROCESSING = 'body-relative-v1'
HAND_PREPROCESSING = 'body-hand-relative-v2'
STABLE_PREPROCESSING = 'stable-body-hand-v3'
FINGER_PREPROCESSING = 'stable-finger-geometry-v4'
DISCRIMINATIVE_PREPROCESSING = 'articulation-motion-v5'


def feature_dimension(preprocessing):
    if preprocessing == DISCRIMINATIVE_PREPROCESSING:
        return FEATURE_DIM + 244
    if preprocessing == FINGER_PREPROCESSING:
        return FEATURE_DIM + 158
    if preprocessing in (HAND_PREPROCESSING, STABLE_PREPROCESSING):
        return FEATURE_DIM + 128
    if preprocessing in (None, PREPROCESSING):
        return FEATURE_DIM
    raise ValueError('Preprocesamiento de modelo desconocido.')


def local_hands(points):
    """Forma relativa a la muñeca, escalada por la palma, sin reflejar ni rotar."""
    local, visible = [], []
    for hand in regions(np.asarray(points, dtype=np.float32))[-2:]:
        present = np.any(hand != 0, axis=(-2, -1))
        scale = np.linalg.norm(hand[..., 9, :] - hand[..., 0, :], axis=-1)
        present &= scale > 1e-4
        relative = (hand - hand[..., :1, :]) / np.maximum(scale[..., None, None], 1e-4)
        relative = np.where(present[..., None, None], relative, 0)
        local.append(relative.reshape(*hand.shape[:-2], 63))
        visible.append(present.astype(np.float32)[..., None])
    return np.concatenate(local + visible, axis=-1)


def prepare_sequence(points, preprocessing=HAND_PREPROCESSING):
    feature_dimension(preprocessing)
    if preprocessing == DISCRIMINATIVE_PREPROCESSING:
        stable = smooth_landmarks(points)
        return np.concatenate([prepare_sequence(points, FINGER_PREPROCESSING), articulation_motion(stable)], axis=-1)
    if preprocessing is None:
        return np.asarray(points, dtype=np.float32)
    if preprocessing in (STABLE_PREPROCESSING, FINGER_PREPROCESSING):
        points = smooth_landmarks(points)
    body = normalize_sequence(points)
    if preprocessing in (STABLE_PREPROCESSING, FINGER_PREPROCESSING):
        normalize_face(body)
    if preprocessing == FINGER_PREPROCESSING:
        return np.concatenate([body, local_hands(points), finger_geometry(points)], axis=-1)
    if preprocessing in (HAND_PREPROCESSING, STABLE_PREPROCESSING):
        return np.concatenate([body, local_hands(points)], axis=-1)
    return body


def hand_descriptor(points, contrastive=False):
    hands = local_hands(points)
    if contrastive:
        hands = np.concatenate([hands, 2 * finger_geometry(points)], axis=-1)
    return np.concatenate([np.median(hands, axis=0), np.std(hands, axis=0)])


def nearest_distance(descriptor, references):
    distances = np.sqrt(np.mean((np.asarray(references) - descriptor) ** 2, axis=1))
    return float(np.mean(np.sort(distances)[:min(3, len(distances))]))


def fit_hand_guard(train_points, train_targets, val_points, val_targets, contrastive=False):
    """Referencias solo de entrenamiento; tolerancia comprobada con validación."""
    train_desc = np.stack([hand_descriptor(p, contrastive) for p in train_points])
    val_desc = np.stack([hand_descriptor(p, contrastive) for p in val_points])
    classes = []
    for label in sorted(np.unique(train_targets)):
        refs = representative_references(train_desc[train_targets == label])
        distances = [nearest_distance(d, np.delete(refs, i, axis=0)) for i, d in enumerate(refs)]
        val_distances = [nearest_distance(d, refs) for d in val_desc[val_targets == label]]
        threshold = max(.035, float(np.quantile(distances, .95)), max(val_distances, default=0)) * 1.25
        classes.append({'references': refs.tolist(), 'max_distance': threshold})
    guard = {'version': 'finger-contrast-v2' if contrastive else 'local-hand-shape-v1', 'classes': classes}
    if contrastive:
        # Validation chooses rejection only; references never include validation/test.
        distances = np.array([[nearest_distance(d, c['references']) for c in classes] for d in val_desc])
        for label, item in enumerate(classes):
            own = distances[:, label]
            rival = np.min(np.delete(distances, label, axis=1), axis=1)
            eligible = []
            for ratio in (.8, .9, .98):
                accepted = (own <= item['max_distance']) & (own < ratio * rival)
                if accepted.sum() >= 3 and np.mean(val_targets[accepted] == label) >= .95:
                    eligible.append(ratio)
            item['max_rival_ratio'] = max(eligible, default=.8)
    return guard


def hand_guard_accept(points, predicted, guard):
    if not guard:
        return True
    item = guard['classes'][int(predicted)]
    contrastive = guard.get('version') == 'finger-contrast-v2'
    descriptor = hand_descriptor(points, contrastive)
    own = nearest_distance(descriptor, item['references'])
    if own > item['max_distance']:
        return False
    if contrastive:
        rival = min(nearest_distance(descriptor, other['references'])
                    for i, other in enumerate(guard['classes']) if i != int(predicted))
        return own < item['max_rival_ratio'] * rival
    return True


def regions(points):
    face_dim = FACE_FULL_DIM if USE_FULL_FACE else FACE_KEY_DIM
    return [points[..., :POSE_DIM].reshape(*points.shape[:-1], 33, 4),
            points[..., POSE_DIM:POSE_DIM + face_dim].reshape(*points.shape[:-1], -1, 3),
            points[..., POSE_DIM + face_dim:POSE_DIM + face_dim + 63].reshape(*points.shape[:-1], 21, 3),
            points[..., -63:].reshape(*points.shape[:-1], 21, 3)]


def normalize_sequence(points):
    """Ancla XY al torso y escala por hombros; conserva movimiento y ausencias."""
    result = np.asarray(points, dtype=np.float32).copy()
    if result.ndim != 2 or result.shape[1] != FEATURE_DIM or not np.isfinite(result).all():
        raise ValueError('Secuencia inválida para normalizar.')
    pose = regions(result)[0]
    shoulders = pose[:, [11, 12], :]
    widths = np.linalg.norm(shoulders[:, 0, :2] - shoulders[:, 1, :2], axis=1)
    valid = np.all(shoulders[:, :, 3] >= .4, axis=1) & (widths >= .03)
    if np.count_nonzero(valid) >= len(result) // 2:
        center = np.median(shoulders[valid, :, :2].mean(axis=1), axis=0)
        scale = float(np.median(widths[valid]))
    else:
        # Si falta el torso, mantener un marco estable en vez de inventar hombros.
        center, scale = np.array([.5, .5], dtype=np.float32), 1.0
    for region in regions(result):
        present = np.any(region[..., :3] != 0, axis=-1)
        region[..., :2] = np.where(present[..., None], (region[..., :2] - center) / scale, 0)
        region[..., 2] = np.where(present, region[..., 2] / scale, 0)
    return result


def augment_viewpoints(points, targets, seed=42):
    """Variaciones XY leves de cámara sobre datos crudos, solo para entrenar.

    Cada toma usa una transformación constante para conservar su movimiento.
    No simula giros 3D ni inventa puntos ocultos; nunca refleja las manos.
    """
    raw = np.asarray(points, dtype=np.float32)
    rng = np.random.default_rng(seed)
    output = [raw.copy()]
    for direction in (-1, 1):
        varied = raw.copy()
        for sequence in varied:
            angle = np.deg2rad(direction * rng.uniform(4, 10))
            cosine, sine = np.cos(angle), np.sin(angle)
            matrix = np.array([[cosine, -sine], [sine, cosine]], dtype=np.float32)
            matrix = matrix @ np.diag([rng.uniform(.95, 1.05), 1.0])
            pose = regions(sequence)[0]
            visible = np.all(pose[:, [11, 12], 3] >= .4, axis=1)
            center = (np.median(pose[visible][:, [11, 12], :2].mean(axis=1), axis=0)
                      if np.any(visible) else np.array([.5, .5]))
            for region in regions(sequence):
                present = np.any(region[..., :3] != 0, axis=-1)
                region[..., :2] = np.where(present[..., None],
                                           (region[..., :2] - center) @ matrix.T + center, 0)
        output.append(varied)
    return np.concatenate(output), np.concatenate([targets] * 3, axis=0)


def augment_training(points, targets, seed=42):
    """Originales + dos variaciones leves. No refleja, invierte ni cambia clases."""
    rng = np.random.default_rng(seed)
    output = [points.copy()]
    for _ in range(2):
        varied = points.copy()
        for sequence in varied:
            scale = rng.uniform(.95, 1.05)
            for region in regions(sequence[:, :FEATURE_DIM]):
                present = np.any(region[..., :3] != 0, axis=-1)
                noise = rng.normal(0, .005, region[..., :3].shape)
                region[..., :3] = np.where(present[..., None], region[..., :3] * scale + noise, 0)
            if sequence.shape[-1] > FEATURE_DIM:
                shapes = sequence[:, FEATURE_DIM:FEATURE_DIM + 126].reshape(len(sequence), 2, 21, 3)
                present = np.any(shapes != 0, axis=-1)
                shapes[:] = np.where(present[..., None], shapes + rng.normal(0, .005, shapes.shape), 0)
        output.append(varied)
    return np.concatenate(output), np.concatenate([targets, targets, targets], axis=0)


def decision_metrics(probabilities, targets, threshold=.85, margin=.15, allowed=None):
    probabilities = np.asarray(probabilities)
    order = np.sort(probabilities, axis=1)
    accepted = (order[:, -1] >= threshold) & ((order[:, -1] - order[:, -2]) >= margin)
    if allowed is not None:
        accepted &= np.asarray(allowed, dtype=bool)
    correct = np.argmax(probabilities, axis=1) == targets
    return {'threshold': threshold, 'margin': margin, 'evaluated': int(len(targets)),
            'accepted': int(accepted.sum()), 'coverage': float(np.mean(accepted)),
            'accepted_accuracy': float(np.mean(correct[accepted])) if accepted.any() else None}


def validation_threshold(probabilities, targets):
    # Ajustar solo con validación. El test queda reservado para el informe final.
    candidates = [decision_metrics(probabilities, targets, threshold) for threshold in [.85, .90, .95]]
    eligible = [m for m in candidates if m['accepted'] >= 3 and m['accepted_accuracy'] >= .9]
    return max(eligible, key=lambda m: m['coverage']) if eligible else candidates[-1]


def smooth_landmarks(points):
    """Filtro causal leve: sin interpolar manos ausentes ni mezclar tomas."""
    result = np.asarray(points, dtype=np.float32).copy()
    for region in regions(result):
        original = region[..., :3].copy()
        present = np.any(original != 0, axis=-1)
        for t in range(1, len(result)):
            keep = present[t] & present[t-1]
            region[t, :, :3] = np.where(keep[:,None], .7*original[t] + .3*region[t-1,:,:3], original[t])
    return result


def normalize_face(body):
    from config import FACE_KEY_INDICES
    face = regions(body)[1]
    eyes = (33,263) if USE_FULL_FACE else (FACE_KEY_INDICES.index(33), FACE_KEY_INDICES.index(263))
    for frame in face:
        present=np.any(frame != 0,axis=1)
        scale=np.linalg.norm(frame[eyes[0],:2]-frame[eyes[1],:2])
        if present.all() and scale>.02:
            center=(frame[eyes[0]]+frame[eyes[1]])/2
            frame[:]=(frame-center)/scale


def temporal_descriptor(points, preprocessing=STABLE_PREPROCESSING, descriptor_version=None):
    if descriptor_version == "trajectory-v2":
        from motion_features import trajectory_descriptor
        return trajectory_descriptor(points)
    if descriptor_version is not None:
        raise ValueError("Versión de trayectoria desconocida.")
    prepared=prepare_sequence(points,preprocessing)
    hands=prepared[:, FEATURE_DIM:FEATURE_DIM+126]
    if hands.shape[1] != 126:
        hands=local_hands(points)[:,:126]
    raw_regions = regions(prepared[:, :FEATURE_DIM])
    wrists = np.concatenate([raw_regions[-2][:,0,:], raw_regions[-1][:,0,:]], axis=1)
    hands = np.concatenate([hands, wrists], axis=1)
    chunks=[np.mean(chunk,axis=0) for chunk in np.array_split(hands,3)]
    velocity=np.diff(hands,axis=0)
    return np.concatenate(chunks+[np.std(hands,axis=0),np.mean(np.abs(velocity),axis=0)])


def fit_temporal_guard(points, targets, validation, val_targets, descriptor_version=None):
    train=np.stack([temporal_descriptor(p, descriptor_version=descriptor_version) for p in points])
    val=np.stack([temporal_descriptor(p, descriptor_version=descriptor_version) for p in validation])
    classes=[]
    for label in sorted(np.unique(targets)):
        refs=representative_references(train[targets==label])
        distances=[nearest_distance(d,np.delete(refs,i,axis=0)) for i,d in enumerate(refs)]
        check=[nearest_distance(d,refs) for d in val[val_targets==label]]
        threshold=max(.04,float(np.quantile(distances,.95)),float(np.quantile(check,.95)) if check else 0)*1.1
        classes.append({'references':refs.tolist(),'max_distance':threshold})
    guard = {'preprocessing':STABLE_PREPROCESSING,'classes':classes,'descriptor_version':descriptor_version}
    if descriptor_version == 'trajectory-v2':
        from motion_features import fit_motion_profile
        moving = set(fit_motion_profile(points, targets)['moving_classes'])
        distances = np.array([[nearest_distance(d, item['references']) for item in classes] for d in val])
        for i,item in enumerate(classes):
            item['motion_required'] = i in moving
            rivals = [j for j in range(len(classes)) if (j in moving) != (i in moving)]
            if not rivals: continue
            own=distances[:,i];rival=distances[:,rivals].min(axis=1)
            same_motion=np.isin(val_targets,list(moving)) == (i in moving)
            eligible=[]
            for ratio in (.8,.9,.98,1.1):
                accepted=(own<=item['max_distance']) & (own<=ratio*np.maximum(rival,1e-8))
                n=int(accepted.sum())
                if n>=3 and same_motion[accepted].mean()>=.95:
                    eligible.append((n,ratio))
            if eligible:
                item['rival_classes']=rivals
                item['motion_rival_ratio']=max(eligible)[1]
    return guard


def temporal_guard_score(points,predicted,guard):
    if not guard: return 0.
    item=guard['classes'][int(predicted)]
    descriptor=temporal_descriptor(points,guard['preprocessing'],guard.get('descriptor_version'))
    own=nearest_distance(descriptor,item['references'])
    score=own/max(item['max_distance'],1e-8)
    if item.get('rival_classes'):
        rival=min(nearest_distance(descriptor,guard['classes'][i]['references']) for i in item['rival_classes'])
        score=max(score,own/max(item['motion_rival_ratio']*rival,1e-8))
    return score


def temporal_guard_accept(points,predicted,guard):
    return temporal_guard_score(points,predicted,guard) <= 1.


def calibrate_decision(probabilities, targets, allowed=None):
    candidates=[]
    for threshold in (.85,.90,.95):
        for margin in (.15,.20,.25):
            metrics=decision_metrics(probabilities,targets,threshold,margin,allowed)
            if metrics['accepted']>=3 and metrics['accepted_accuracy']>=.95:
                candidates.append(metrics)
    return max(candidates,key=lambda m:(m['coverage'],m['accepted_accuracy'],m['margin'])) if candidates else decision_metrics(probabilities,targets,.95,.25,allowed)


def finger_geometry(points):
    """30 scalars: extension of each finger and pairwise fingertip separation.

    Distances use palm units; extension uses endpoint / bone-chain length.
    Translation/scale invariant, no handedness swap or orientation removal from
    the original channels. Missing hands remain zero. Shared train/inference.
    """
    output = []
    tips = [4, 8, 12, 16, 20]
    for hand in regions(np.asarray(points, dtype=np.float32))[-2:]:
        scale = np.linalg.norm(hand[..., 9, :] - hand[..., 0, :], axis=-1)
        present = scale > 1e-4
        features = []
        for tip in tips:
            chain = hand[..., [0, tip-3, tip-2, tip-1, tip], :]
            length = np.linalg.norm(np.diff(chain, axis=-2), axis=-1).sum(axis=-1)
            extension = np.linalg.norm(hand[..., tip, :] - hand[..., 0, :], axis=-1)
            features.append(extension / np.maximum(length, 1e-4))
        for i, tip in enumerate(tips):
            for other in tips[i+1:]:
                distance = np.linalg.norm(hand[..., tip, :] - hand[..., other, :], axis=-1)
                features.append(distance / np.maximum(scale, 1e-4))
        output.append(np.where(present[..., None], np.stack(features, axis=-1), 0))
    return np.concatenate(output, axis=-1).astype(np.float32)


def articulation_motion(points):
    """86 channels. Retain orientation and handedness; never align/reflect palms.

    Each hand: 15 bend cosines, 5 tip/palm distances, 9 palm basis components,
    2 body-relative wrist velocities, 10 local fingertip velocities. Then the
    2D inter-hand vector and face position. MediaPipe hand Z origins differ:
    cross-hand and body relationships deliberately use XY only.
    """
    raw=np.asarray(points,dtype=np.float32)
    body=normalize_sequence(raw)
    raw_hands=regions(raw)[-2:];body_hands=regions(body)[-2:]
    output=[];presence=[]
    def unit(v):return v/np.maximum(np.linalg.norm(v,axis=-1,keepdims=True),1e-5)
    def velocity(v, present):
        delta=np.zeros_like(v)
        delta[1:]=np.where((present[1:]&present[:-1])[:,None],v[1:]-v[:-1],0)
        return delta
    for hand,relative in zip(raw_hands,body_hands):
        palm=np.linalg.norm(hand[:,9]-hand[:,0],axis=-1)
        present=palm>1e-4;presence.append(present)
        local=(hand-hand[:,:1])/np.maximum(palm[:,None,None],1e-4)
        bends=[]
        for base in (1,5,9,13,17):
            chain=hand[:,[0,base,base+1,base+2,base+3]]
            bones=unit(np.diff(chain,axis=1))
            bends.extend([np.sum(bones[:,j]*bones[:,j+1],axis=-1) for j in range(3)])
        tips=local[:,[4,8,12,16,20]]
        up=unit(local[:,9]);across=unit(local[:,5]-local[:,17]);normal=unit(np.cross(across,up))
        descriptor=np.concatenate([np.stack(bends,axis=-1),np.linalg.norm(tips,axis=-1),up,across,normal,
                                   velocity(relative[:,0,:2],present),velocity(tips[:,:,:2].reshape(len(raw),10),present)],axis=-1)
        output.append(np.where(present[:,None],descriptor,0))
    together=presence[0]&presence[1]
    output.append(np.where(together[:,None],body_hands[1][:,0,:2]-body_hands[0][:,0,:2],0))
    face=regions(body)[1]
    valid=np.any(face!=0,axis=(1,2))
    output.append(np.where(valid[:,None],np.mean(face[:,:,:2],axis=1),0))
    return np.nan_to_num(np.concatenate(output,axis=-1)).astype(np.float32)


def augment_articulation(points, targets, seed=42):
    """Small temporally correlated noise in palm units; preserve finger shape."""
    rng=np.random.default_rng(seed);output=[points.copy()]
    for _ in range(2):
        varied=points.copy()
        for sequence in varied:
            for index,region in enumerate(regions(sequence)):
                present=np.any(region[...,:3]!=0,axis=-1)
                scale=float(np.median(np.linalg.norm(region[:,9,:3]-region[:,0,:3],axis=-1))) if index>=2 else .2
                noise=rng.normal(0,max(scale,1e-4)*.003,region[...,:3].shape).astype(np.float32)
                for t in range(1,len(noise)):noise[t]=.7*noise[t-1]+.3*noise[t]
                region[...,:3]=np.where(present[...,None],region[...,:3]+noise,0)
        output.append(varied)
    return np.concatenate(output),np.concatenate([targets]*3)


def representative_references(references, limit=64):
    """Bound guard inference cost; deterministic farthest-point coverage."""
    refs=np.asarray(references)
    if len(refs)<=limit:return refs
    selected=[int(np.argmin(np.sum((refs-np.median(refs,axis=0))**2,axis=1)))]
    distances=np.full(len(refs),np.inf)
    for _ in range(limit-1):
        distances=np.minimum(distances,np.mean((refs-refs[selected[-1]])**2,axis=1))
        distances[selected]=-1
        selected.append(int(np.argmax(distances)))
    return refs[selected]
