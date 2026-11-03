"""Controles geométricos compartidos. No dibuja ni guarda imágenes."""
import numpy as np
from recognition_features import regions


# Comprueba manos completas, tamaño de palma, límites del encuadre y visibilidad del torso.
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


# Mide brillo y variación del Laplaciano para advertir oscuridad, exceso de luz o poco enfoque.
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


# Resume la proporción de detecciones utilizables y advierte movimiento al final de una toma.
def sequence_quality(points):
    reports = [landmark_quality(frame) for frame in points]
    ratio = float(np.mean([r['usable'] for r in reports]))
    hands = regions(np.asarray(points))[-2:]
    trajectory = np.concatenate([hand[:,0,:2] for hand in hands], axis=1)
    motion = np.linalg.norm(np.diff(trajectory, axis=0), axis=1)
    end_motion = float(np.mean(motion[-4:])) if len(motion) else 0
    return {'boundary_warning': end_motion > .03, 'end_motion': round(end_motion,4), 'usable_ratio': round(ratio,3), 'low_quality': ratio < .8,
            'message': 'Repite la toma con las manos completas y dentro del encuadre.' if ratio < .8 else 'Encuadre válido.'}


# Evalúa luz y enfoque dentro de las regiones de manos, usando las mismas coordenadas que el detector.
def hand_image_quality(image, points):
    """Inspect actual hand regions in the SAME mirrored coordinate frame.

    A dark/textureless wall should not veto a well-lit, focused hand. Keep the
    original image-quality thresholds and inspect each visible hand separately.
    """
    pose, face, left, right = regions(np.asarray(points, np.float32))
    height, width = image.shape[:2]
    reports = []
    for hand in (left, right):
        if not np.any(hand) or not np.isfinite(hand).all():
            continue
        low = hand[:, :2].min(axis=0); high = hand[:, :2].max(axis=0)
        pad = np.maximum((high-low)*.2, .01)
        x0,y0 = np.floor(np.maximum(low-pad,0)*[width,height]).astype(int)
        x1,y1 = np.ceil(np.minimum(high+pad,1)*[width,height]).astype(int)
        if x1-x0 >= 12 and y1-y0 >= 12:
            reports.append(image_quality(image[y0:y1,x0:x1]))
    if not reports:
        return {**image_quality(image), 'scope':'frame'}
    warnings = list(dict.fromkeys(message for report in reports for message in report['warnings']))
    return {'scope':'hands','brightness':min(report['brightness'] for report in reports),
            'sharpness':min(report['sharpness'] for report in reports),'warnings':warnings,
            'hands_evaluated':len(reports)}
