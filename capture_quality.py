"""Controles geométricos compartidos. No dibuja ni guarda imágenes."""
import numpy as np
from recognition_features import regions


def landmark_quality(points):
    pose, _, left, right = regions(np.asarray(points, dtype=np.float32))
    hands = [h for h in (left, right) if np.any(h != 0)]
    issues = []
    if not hands:
        issues.append('Coloca al menos una mano dentro del encuadre.')
    complete = 0
    for hand in hands:
        finite = np.isfinite(hand).all()
        inside = np.mean(np.all((hand[:, :2] >= .015) & (hand[:, :2] <= .985), axis=1))
        palm = np.linalg.norm(hand[9] - hand[0])
        distinct = len(np.unique(np.round(hand, 5), axis=0))
        if not finite or inside < .95 or np.any(hand[:, :2] < 0) or np.any(hand[:, :2] > 1):
            issues.append('Aleja la mano del borde: hay dedos fuera de cuadro.')
        elif palm < .008 or distinct < 15:
            issues.append('Acerca un poco la mano y muestra los dedos completos.')
        else:
            complete += 1
    torso = bool(np.all(pose[[11,12],3] >= .4))
    if not torso:
        issues.append('Incluye los hombros en el encuadre para estabilizar la posición.')
    usable = bool(complete and complete == len(hands))
    return {'usable': usable, 'hands': len(hands), 'torso': torso,
            'score': round((1.0 if usable else .2 if hands else 0) * (1 if torso else .85), 2),
            'message': issues[0] if issues else 'Buen encuadre. Haz la seña completa.', 'issues': list(dict.fromkeys(issues))}


def image_quality(image):
    import cv2
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    messages = []
    if brightness < 35:
        messages.append('Falta luz. Ilumina las manos de frente.')
    elif brightness > 235:
        messages.append('Hay demasiada luz. Evita el contraluz o la sobreexposición.')
    if sharpness < 8:
        messages.append('La imagen está poco definida. Revisa el enfoque y limpia la cámara.')
    return {'brightness': round(brightness,1), 'sharpness': round(sharpness,1), 'warnings': messages}


def sequence_quality(points):
    reports = [landmark_quality(frame) for frame in points]
    ratio = float(np.mean([r['usable'] for r in reports]))
    hands = regions(np.asarray(points))[-2:]
    trajectory = np.concatenate([hand[:,0,:2] for hand in hands], axis=1)
    motion = np.linalg.norm(np.diff(trajectory, axis=0), axis=1)
    end_motion = float(np.mean(motion[-4:])) if len(motion) else 0
    return {'boundary_warning': end_motion > .03, 'end_motion': round(end_motion,4), 'usable_ratio': round(ratio,3), 'low_quality': ratio < .8,
            'message': 'Repite la toma con las manos completas y dentro del encuadre.' if ratio < .8 else 'Encuadre válido.'}
