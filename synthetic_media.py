"""Convierte fotos y videos en secuencias con el mismo formato que la cámara.

Usa exactamente la detección de la cámara (MediaPipe Holistic, recuperación y
refinamiento de manos de ``web_app.Runtime``) y la misma vista en espejo, para
que los puntos coincidan con los grabados en vivo.

  · Foto  → una postura. Sirve solo para señas estáticas: la secuencia de 30
            fotogramas repite la postura y el generador añade micro‑variaciones,
            nunca movimiento.
  · Video → se muestrea a la misma frecuencia de captura (10 fps × salto del
            perfil), se recorta al tramo con manos y se lleva a 30 fotogramas.
"""
from __future__ import annotations

import os
import tempfile
import time

import numpy as np

from config import FEATURE_DIM, SEQUENCE_LENGTH
from sign_languages import CAPTURE_FPS, frame_stride

MAX_IMAGE_SIDE = 1920
MAX_VIDEO_SECONDS = 20
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.m4v', '.webm', '.avi', '.mkv')
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')


class MediaError(ValueError):
    pass


def _fit(image):
    height, width = image.shape[:2]
    scale = min(1., MAX_IMAGE_SIDE / max(height, width))
    if scale < 1:
        import cv2
        image = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    return image


def _rig(results):
    from rig_overlay import upper_body_rig
    hands = []
    for side in ('left_hand_landmarks', 'right_hand_landmarks'):
        hand = getattr(results, side, None)
        hands.append([[round(float(p.x), 5), round(float(p.y), 5)] for p in hand.landmark] if hand else None)
    return {'hands': hands, 'body': upper_body_rig(getattr(results, 'pose_landmarks', None))}


class Detector:
    """Detección igual a la de la cámara, reutilizando una sesión de Seña."""

    def __init__(self, language, static):
        import mediapipe as mp
        import web_app
        self.runtime = web_app.RUNTIME
        self.session = web_app.Session(language)
        self.session.holistic = mp.solutions.holistic.Holistic(
            static_image_mode=static, model_complexity=1,
            min_detection_confidence=.5, min_tracking_confidence=.5)
        self.clock = 1000.

    def __call__(self, image, mirror=True):
        import cv2
        from utils import extract_keypoints, hands_detected, mediapipe_detection
        from capture_quality import landmark_quality
        view = cv2.flip(image, 1) if mirror else image.copy()
        _, results = mediapipe_detection(view, self.session.holistic)
        self.clock += 1 / CAPTURE_FPS
        results, _ = self.runtime.recover_hand_tracking(self.session, view, results, self.clock)
        points = extract_keypoints(results).astype(np.float32)
        hands = [getattr(results, side, None) is not None for side in ('left_hand_landmarks', 'right_hand_landmarks')]
        return {'points': points, 'hands': hands, 'any_hand': hands_detected(results),
                'quality': landmark_quality(points), 'rig': _rig(results)}

    def close(self):
        self.session.close()
        try:
            self.session.holistic.close()
        except Exception:
            pass


def decode_image(data):
    import cv2
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise MediaError('No se pudo leer la imagen. Usa JPG, PNG o WEBP.')
    return _fit(image)


LIGHTING_PROFILES = ('luz_baja', 'luz_intensa', 'sombra_lateral')


def change_lighting(image, profile=None):
    """Modifica píxeles BGR antes de MediaPipe, sin añadir puntos artificiales."""
    if profile is None:
        return image
    pixels = image.astype(np.float32)
    if profile == 'luz_baja':
        pixels = pixels * .65
    elif profile == 'luz_intensa':
        pixels = pixels * 1.15 + 20
    elif profile == 'sombra_lateral':
        gradient = np.linspace(.55, 1., image.shape[1], dtype=np.float32)
        pixels *= gradient[None, :, None]
    else:
        raise MediaError('Escenario de iluminación desconocido.')
    return np.clip(pixels, 0, 255).astype(np.uint8)


def image_source(data, language, mirror=True, lighting=None):
    """Foto → postura estática (30 fotogramas iguales) con su esqueleto detectado."""
    image = change_lighting(decode_image(data), lighting)
    detector = Detector(language, static=True)
    try:
        found = detector(image, mirror)
    finally:
        detector.close()
    warnings = []
    if not found['any_hand']:
        raise MediaError('No se detectó ninguna mano en la imagen. Usa una foto con la mano completa y buena luz.')
    if not found['quality']['usable']:
        warnings.append(found['quality'].get('message') or 'La detección de la mano es incompleta.')
    if found['points'][:132].reshape(33, 4)[[11, 12], :2].sum() == 0:
        warnings.append('No se ve el torso: el modelo usa la posición respecto al cuerpo. Encuadra hombros y mano.')
    sequence = np.repeat(found['points'][None], SEQUENCE_LENGTH, axis=0)
    return {'kind': 'image', 'static': True, 'sequence': sequence, 'frames_read': 1,
            'frames_with_hands': 1, 'hands': found['hands'], 'warnings': warnings,
            'preview': [found['rig']], 'size': list(image.shape[1::-1])}


def _sample_video(path, stride, progress=None, cancelled=None, mirror=True, language='lsm', lighting=None):
    import cv2
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise MediaError('No se pudo abrir el video. Usa MP4 (H.264), MOV o WEBM.')
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total and total / fps > MAX_VIDEO_SECONDS:
        capture.release()
        raise MediaError(f'El video dura más de {MAX_VIDEO_SECONDS} s. Recórtalo a la seña (1–6 s).')
    step = fps / CAPTURE_FPS  # mismo ritmo que la cámara de Seña
    detector = Detector(language, static=False)
    frames, rigs, hands_seen = [], [], []
    next_time, index = 0., 0
    try:
        while True:
            if cancelled and cancelled():
                raise MediaError('Importación cancelada.')
            ok, image = capture.read()
            if not ok:
                break
            if index + 1e-6 >= next_time:
                next_time += step
                found = detector(change_lighting(_fit(image), lighting), mirror)
                frames.append(found['points'])
                rigs.append(found['rig'])
                hands_seen.append(found['hands'])
                if progress:
                    progress(index, total)
            index += 1
    finally:
        capture.release()
        detector.close()
    if not frames:
        raise MediaError('El video no tiene fotogramas legibles.')
    return np.stack(frames), rigs, hands_seen, fps


def video_source(data, language, suffix='.mp4', mirror=True, progress=None, cancelled=None, lighting=None):
    """Video → secuencia real de 30 fotogramas al ritmo de la cámara."""
    stride = frame_stride(language)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(data)
        path = handle.name
    try:
        frames, rigs, hands_seen, fps = _sample_video(path, stride, progress, cancelled, mirror, language, lighting)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return sequence_from_frames(frames, rigs, hands_seen, stride)


MAX_CAMERA_FRAMES = MAX_VIDEO_SECONDS * CAPTURE_FPS


def camera_source(images, language, progress=None, cancelled=None, lighting=None):
    """Grabación desde la cámara del navegador: fotogramas JPEG a 10 fps, sin espejo.

    Es exactamente lo que recibe /api/frame al reconocer, así que se refleja
    igual que la cámara y se trata como un video real."""
    if not images:
        raise MediaError('La grabación no tiene fotogramas.')
    if len(images) > MAX_CAMERA_FRAMES:
        raise MediaError(f'La grabación dura más de {MAX_VIDEO_SECONDS} s.')
    detector = Detector(language, static=False)
    frames, rigs, hands_seen = [], [], []
    try:
        for index, data in enumerate(images):
            if cancelled and cancelled():
                raise MediaError('Importación cancelada.')
            found = detector(change_lighting(decode_image(data), lighting), mirror=True)
            frames.append(found['points'])
            rigs.append(found['rig'])
            hands_seen.append(found['hands'])
            if progress:
                progress(index, len(images))
    finally:
        detector.close()
    result = sequence_from_frames(np.stack(frames), rigs, hands_seen, frame_stride(language))
    result['kind'] = 'camera'
    return result


def sequence_from_frames(frames, rigs, hands_seen, stride=1):
    """Recorta al tramo con manos y lo lleva a 30 fotogramas guardados."""
    present = np.array([any(h) for h in hands_seen])
    warnings = []
    if not present.any():
        raise MediaError('No se detectaron manos. Encuadra hombros y manos con buena luz de frente.')
    first, last = np.flatnonzero(present)[[0, -1]]
    # Conservar un poco de reposo antes y después, como en la grabación en vivo.
    first, last = max(0, first - 2 * stride), min(len(frames) - 1, last + 2 * stride)
    active = frames[first:last + 1][::stride]
    rig_active = rigs[first:last + 1][::stride]
    hand_ratio = float(present[first:last + 1].mean())
    if hand_ratio < .8:
        warnings.append(f'Las manos se perdieron en {round((1 - hand_ratio) * 100)} % del tramo; revisa luz y encuadre.')
    n = len(active)
    if n < SEQUENCE_LENGTH // 2:
        raise MediaError(f'El tramo con manos dura {n / CAPTURE_FPS * stride:.1f} s; se necesitan al menos '
                         f'{SEQUENCE_LENGTH / 2 / CAPTURE_FPS * stride:.1f} s.')
    if n > SEQUENCE_LENGTH * 1.5:
        warnings.append(f'El tramo con manos dura {n / CAPTURE_FPS * stride:.1f} s; se comprimió a '
                        f'{SEQUENCE_LENGTH / CAPTURE_FPS * stride:.0f} s. Si contiene varias señas, recórtalo.')
    if n < SEQUENCE_LENGTH:
        # Sostener la postura inicial y final, como el reposo de una toma en vivo.
        before = (SEQUENCE_LENGTH - n) // 2
        index = np.r_[np.zeros(before, int), np.arange(n), np.full(SEQUENCE_LENGTH - n - before, n - 1)]
    else:
        index = np.round(np.linspace(0, n - 1, SEQUENCE_LENGTH)).astype(int)
    sequence = active[index].astype(np.float32)
    preview = [rig_active[i] for i in index]
    visible = np.any(sequence[:, 366:] != 0, axis=1)
    if visible.mean() < .8:
        raise MediaError('Faltan manos en demasiados fotogramas para formar una toma válida.')
    return {'kind': 'video', 'static': False, 'sequence': sequence, 'frames_read': len(frames),
            'frames_with_hands': int(present.sum()), 'hands': [bool(np.any(sequence[:, r] != 0))
                                                                for r in (slice(366, 429), slice(429, 492))],
            'warnings': warnings, 'preview': preview}


def kind_for(name, content_type=''):
    lower = (name or '').lower()
    if lower.endswith(VIDEO_EXTENSIONS) or content_type.startswith('video/'):
        return 'video'
    if lower.endswith(IMAGE_EXTENSIONS) or content_type.startswith('image/'):
        return 'image'
    raise MediaError('Formato no compatible. Usa fotos (JPG, PNG, WEBP) o videos (MP4, MOV, WEBM).')
