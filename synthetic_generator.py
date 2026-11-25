"""Motor de datos sintéticos para LSM: variaciones anatómicas de landmarks.

Trabaja sobre el mismo formato del dataset: secuencias (30, 492) con
  [0:132]   cuerpo 33 × (x, y, z, visibilidad)
  [132:366] rostro 78 × (x, y, z)
  [366:429] mano izquierda 21 × (x, y, z)
  [429:492] mano derecha 21 × (x, y, z)
en coordenadas de imagen normalizadas (ya en espejo, igual que la cámara).

Principios:
  · La forma de la mano se reconstruye hueso por hueso conservando la DIRECCIÓN
    de cada hueso: cambian tamaños y proporciones, no la configuración.
  · Nunca se intercambia la mano dominante ni se refleja la seña.
  · Las rotaciones son pequeñas y en el plano de la imagen; la «perspectiva»
    usa z de MediaPipe solo como aproximación y se limita a pocos grados.
  · Una seña estática (foto) recibe solo micro‑variaciones por fotograma; no
    se inventa movimiento.
  · Cada muestra se valida (anatomía, rango, coherencia temporal, geometría de
    dedos y duplicados) y las rechazadas se cuentan por motivo.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, asdict, field

import numpy as np

from config import FEATURE_DIM, SEQUENCE_LENGTH

POSE = slice(0, 132)
FACE = slice(132, 366)
HANDS = (slice(366, 429), slice(429, 492))
FINGERS = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16], [17, 18, 19, 20]]
BONES = [(0, f[0]) for f in FINGERS] + [(a, b) for f in FINGERS for a, b in zip(f, f[1:])]
TIPS = [4, 8, 12, 16, 20]

# Señas que el modelo actual confunde entre sí: variaciones mínimas en dedos.
CONFUSABLE_GROUPS = [{'B', 'E'}, {'G', 'H'}, {'N', 'M', 'Ñ'}, {'U', 'V', 'W', 'R'}, {'S', 'T', 'A'}, {'F', 'B'}]


@dataclass(frozen=True)
class Level:
    name: str
    body_scale: float      # distancia a la cámara (± fracción)
    shift: float           # desplazamiento de todo el cuerpo (unidades de imagen)
    roll_deg: float        # inclinación leve de la cámara
    hand_scale: float      # tamaño de mano (± fracción)
    palm: float            # proporción de la palma (± fracción)
    finger: float          # largo de cada dedo (± fracción)
    spread_deg: float      # separación/flexión leve de cada dedo en el plano
    hand_roll_deg: float   # giro de la mano alrededor de la muñeca
    yaw_deg: float         # perspectiva aproximada (escorzo horizontal)
    noise: float           # ruido de detección (fracción del tamaño de la palma)
    speed: float           # variación de velocidad (± fracción)
    offset: int            # desfase temporal máximo (fotogramas)
    geometry_tolerance: float  # cambio máximo permitido en la geometría de dedos


LEVELS = {
    'conservador': Level('conservador', .04, .025, 0, .04, .03, .03, 0, 3, 0, .010, .05, 1, .06),
    'equilibrado': Level('equilibrado', .20, .09, 3, .14, .06, .06, 3, 7, 6, .018, .15, 2, .10),
    'avanzado':    Level('avanzado',    .30, .14, 5, .20, .09, .09, 5, 12, 12, .025, .25, 3, .14),
}
DEFAULT_LEVEL = 'equilibrado'


def label_is_confusable(text):
    text = str(text or '').strip().upper()
    return any(text in group for group in CONFUSABLE_GROUPS)


def _hand(frame, index):
    return frame[HANDS[index]].reshape(21, 3)


def _present(hand):
    return bool(np.any(hand != 0))


def _rot2(points, center, degrees):
    if not degrees:
        return points
    angle = np.deg2rad(degrees)
    c, s = np.cos(angle), np.sin(angle)
    out = points.copy()
    dx, dy = points[..., 0] - center[0], points[..., 1] - center[1]
    out[..., 0] = center[0] + c * dx - s * dy
    out[..., 1] = center[1] + s * dx + c * dy
    return out


def torso_center(sequence):
    """Centro de hombros promedio (o centro de la imagen si no hay cuerpo)."""
    pose = sequence[:, POSE].reshape(len(sequence), 33, 4)
    shoulders = pose[:, [11, 12], :2]
    valid = np.all(shoulders != 0, axis=(1, 2))
    if valid.any():
        return shoulders[valid].mean(axis=(0, 1))
    return np.array([.5, .5], np.float32)


@dataclass
class Params:
    """Transformación aplicada a una muestra (se guarda en sus metadatos)."""
    body_scale: float = 1.
    shift: tuple = (0., 0.)
    roll_deg: float = 0.
    hands: list = field(default_factory=list)   # por mano: dict con escala, palma, dedos, giros
    speed: float = 1.
    offset: int = 0
    noise: float = 0.
    seed: int = 0
    scenario: str = 'variacion'
    illumination: str = 'original'

    def summary(self):
        data = asdict(self)
        data['shift'] = [round(float(v), 4) for v in self.shift]
        for key in ('body_scale', 'roll_deg', 'speed', 'noise'):
            data[key] = round(float(data[key]), 4)
        data['hands'] = [{k: (round(float(v), 4) if np.isscalar(v) else [round(float(x), 4) for x in v])
                          for k, v in hand.items()} for hand in self.hands]
        return data


def sample_params(level: Level, rng: np.random.Generator, static: bool, confusable: bool) -> Params:
    u = lambda amount: float(rng.uniform(-amount, amount))
    finger_amount = min(level.finger, LEVELS['conservador'].finger) if confusable else level.finger
    spread = 0. if confusable else level.spread_deg
    hands = []
    for _ in range(2):
        hands.append(dict(scale=1 + u(level.hand_scale), palm=1 + u(level.palm),
                          fingers=[1 + u(finger_amount) for _ in range(5)],
                          spread=[u(spread) for _ in range(5)],
                          roll=u(level.hand_roll_deg), yaw=u(level.yaw_deg)))
    return Params(body_scale=1 + u(level.body_scale), shift=(u(level.shift), u(level.shift)),
                  roll_deg=u(level.roll_deg), hands=hands,
                  speed=1. if static else 1 + u(level.speed),
                  offset=0 if static else int(rng.integers(-level.offset, level.offset + 1)),
                  noise=level.noise, seed=int(rng.integers(0, 2**31 - 1)))


SCENARIOS = (
    'cerca', 'lejos', 'mano_pequena', 'mano_grande',
    'izquierda', 'derecha', 'arriba', 'abajo',
    'camara_inclinada_izquierda', 'camara_inclinada_derecha',
    'perspectiva_izquierda', 'perspectiva_derecha', 'combinado',
)


def scenario_params(level, rng, static, confusable, index):
    """Distribuye escenarios; cada transformación se mantiene durante toda la toma."""
    params = sample_params(level, rng, static, confusable)
    params.scenario = SCENARIOS[index % len(SCENARIOS)]
    name = params.scenario
    amount = float(rng.uniform(.65, 1.))
    if name in ('cerca', 'lejos'):
        direction = 1 if name == 'cerca' else -1
        params.body_scale = 1 + direction * level.body_scale * amount
    elif name in ('mano_pequena', 'mano_grande'):
        direction = 1 if name == 'mano_grande' else -1
        for hand in params.hands:
            hand['scale'] = 1 + direction * level.hand_scale * amount
    elif name in ('izquierda', 'derecha', 'arriba', 'abajo'):
        axis = 0 if name in ('izquierda', 'derecha') else 1
        direction = -1 if name in ('izquierda', 'arriba') else 1
        shift = list(params.shift)
        shift[axis] = direction * level.shift * amount
        params.shift = tuple(shift)
    elif name.startswith('camara_inclinada'):
        params.roll_deg = (-1 if name.endswith('izquierda') else 1) * level.roll_deg * amount
    elif name.startswith('perspectiva'):
        for hand in params.hands:
            hand['yaw'] = (-1 if name.endswith('izquierda') else 1) * level.yaw_deg * amount
    return params


def rebuild_hand(hand, scale, palm, fingers, spread):
    """Reconstruye la mano hueso por hueso: conserva la dirección de cada hueso."""
    wrist = hand[0]
    out = np.zeros_like(hand)
    out[0] = wrist
    for f, chain in enumerate(FINGERS):
        base = chain[0]
        out[base] = wrist + (hand[base] - wrist) * scale * palm
        previous = base
        for joint in chain[1:]:
            bone = (hand[joint] - hand[previous]) * scale * fingers[f]
            if spread[f]:
                bone = _rot2(bone[None], np.zeros(2), spread[f])[0]
            out[joint] = out[previous] + bone
            previous = joint
    return out


def perspective(hand, degrees):
    """Escorzo horizontal aproximado alrededor de la muñeca usando z relativa."""
    if not degrees:
        return hand
    angle = np.deg2rad(degrees)
    out = hand.copy()
    rel = hand - hand[0]
    out[:, 0] = hand[0, 0] + rel[:, 0] * np.cos(angle) + rel[:, 2] * np.sin(angle)
    out[:, 2] = hand[0, 2] - rel[:, 0] * np.sin(angle) + rel[:, 2] * np.cos(angle)
    return out


def time_warp(sequence, speed, offset):
    """Cambia la velocidad alrededor del centro y desfasa; los bordes se sostienen."""
    n = len(sequence)
    t = np.arange(n, dtype=np.float32)
    source = np.clip((t - (n - 1) / 2) * speed + (n - 1) / 2 - offset, 0, n - 1)
    low = np.floor(source).astype(int)
    high = np.minimum(low + 1, n - 1)
    weight = (source - low)[:, None]
    lo, hi = sequence[low], sequence[high]
    # Interpolar solo donde ambos fotogramas tienen la región; si no, el más cercano.
    both = np.any(lo != 0, axis=1) & np.any(hi != 0, axis=1)
    blended = lo * (1 - weight) + hi * weight
    nearest = np.where((weight < .5), lo, hi)
    out = np.where(both[:, None], blended, nearest)
    # Una región ausente en cualquiera de los dos queda como en el más cercano.
    for region in (POSE, FACE, *HANDS):
        missing = ~(np.any(lo[:, region] != 0, axis=1) & np.any(hi[:, region] != 0, axis=1))
        out[missing, region] = nearest[missing, region]
    return out.astype(np.float32)


def apply(sequence, params: Params):
    """Aplica una transformación completa a una secuencia (30, 492)."""
    sequence = np.asarray(sequence, np.float32)
    rng = np.random.default_rng(params.seed)
    out = time_warp(sequence, params.speed, params.offset) if (params.speed != 1 or params.offset) else sequence.copy()
    center = torso_center(sequence)
    for t in range(len(out)):
        frame = out[t]
        for index in range(2):
            hand = _hand(frame, index)
            if not _present(hand):
                continue
            h = params.hands[index]
            new = rebuild_hand(hand, h['scale'], h['palm'], h['fingers'], h['spread'])
            new = _rot2(new, new[0], h['roll'])
            new = perspective(new, h['yaw'])
            palm = np.linalg.norm(new[9, :2] - new[0, :2])
            new[:, :2] += rng.normal(0, params.noise * palm, size=(21, 2))
            frame[HANDS[index]] = new.reshape(-1)
        # Cámara: escala (distancia), inclinación y desplazamiento de todo lo visible.
        for region, width in ((POSE, 4), (FACE, 3), (HANDS[0], 3), (HANDS[1], 3)):
            block = frame[region].reshape(-1, width)
            if not np.any(block[:, :3] != 0):
                continue
            present = np.any(block[:, :3] != 0, axis=1)
            xy = block[present, :2]
            xy = center + (xy - center) * params.body_scale
            xy = _rot2(xy, center, params.roll_deg)
            block[present, :2] = xy + np.asarray(params.shift, np.float32)
            block[present, 2] *= params.body_scale
            frame[region] = block.reshape(-1)
    return out.astype(np.float32)


# ── Validación ──────────────────────────────────────────────────────────────

def _bone_lengths(hand):
    return np.array([np.linalg.norm(hand[b, :2] - hand[a, :2]) for a, b in BONES])


def _bone_angles(hand):
    return np.array([np.arctan2(*(hand[b, 1::-1] - hand[a, 1::-1])) for a, b in BONES])


def finger_signature(sequence):
    """Geometría de dedos invariante a escala (extensión y separación de puntas)."""
    from recognition_features import finger_geometry
    return finger_geometry(sequence)


def motion_extent(sequence):
    """Recorrido máximo de las muñecas (para distinguir señas estáticas y dinámicas)."""
    extents = []
    for index in range(2):
        wrists = sequence[:, HANDS[index]][:, :2]
        visible = np.any(sequence[:, HANDS[index]] != 0, axis=1)
        if visible.sum() >= 2:
            extents.append(float(np.max(np.ptp(wrists[visible], axis=0))))
    return max(extents, default=0.)


@dataclass
class Validator:
    level: Level
    confusable: bool = False
    min_distance: float = .008

    def check(self, original, sample, reference=None):
        """Devuelve None si la muestra es válida; si no, el código del motivo.

        ``reference`` es el original con la misma deformación temporal: la anatomía
        se compara fotograma a fotograma contra él, no contra otro instante."""
        aligned = original if reference is None else reference
        if sample.shape != (SEQUENCE_LENGTH, FEATURE_DIM):
            return 'dimensiones'
        if not np.isfinite(sample).all():
            return 'valores_invalidos'
        # Las regiones ausentes siguen ausentes y las presentes, presentes.
        for region in (POSE, FACE, *HANDS):
            if (np.any(aligned[:, region] != 0, axis=1) != np.any(sample[:, region] != 0, axis=1)).mean() > .1:
                return 'detecciones_alteradas'
        hands_xy = np.concatenate([sample[:, r].reshape(-1, 21, 3)[..., :2] for r in HANDS], axis=1)
        present = np.any(hands_xy != 0, axis=-1)
        if present.any() and (hands_xy[present].min() < -.08 or hands_xy[present].max() > 1.08):
            return 'fuera_de_cuadro'
        limit_scale = 1 + 2.2 * max(self.level.hand_scale, self.level.body_scale) + self.level.palm
        angle_limit = np.deg2rad(self.level.hand_roll_deg + self.level.spread_deg + self.level.yaw_deg + 15)
        for index in range(2):
            ratios, angles = [], []
            for t in range(len(sample)):
                a, b = _hand(aligned[t], index), _hand(sample[t], index)
                if not (_present(a) and _present(b)):
                    continue
                la, lb = _bone_lengths(a), _bone_lengths(b)
                palm = max(np.linalg.norm(a[9, :2] - a[0, :2]), 1e-6)
                # Los huesos muy cortos son sensibles al ruido de detección: se omiten.
                ratios.append(np.where(la > .2 * palm, lb / np.maximum(la, 1e-9), np.nan))
                angles.append(np.where(la > .2 * palm, np.abs(np.angle(np.exp(1j * (_bone_angles(b) - _bone_angles(a))))), np.nan))
            if not ratios:
                continue
            # Mediana a lo largo del tiempo: robusta al ruido de un fotograma aislado.
            with np.errstate(all='ignore'):
                ratio = np.array([np.median(column[np.isfinite(column)]) for column in np.array(ratios).T if np.isfinite(column).any()])
            ratio = ratio[np.isfinite(ratio)]
            if ratio.size and (ratio.min() < 1 / limit_scale or ratio.max() > limit_scale):
                return 'proporciones'
            rel = ratio / max(np.median(ratio), 1e-6)
            if rel.size and (rel.min() < .75 or rel.max() > 1.33):
                return 'deformacion'
            with np.errstate(all='ignore'):
                angle = np.array([np.median(column[np.isfinite(column)]) for column in np.array(angles).T if np.isfinite(column).any()])
            angle = angle[np.isfinite(angle)]
            if angle.size and angle.max() > angle_limit:
                return 'angulos'
        # Geometría de dedos (lo que distingue B de E, M de N…).
        tolerance = self.level.geometry_tolerance * (.6 if self.confusable else 1.)
        ga, gb = finger_signature(aligned), finger_signature(sample)
        mask = (ga != 0) & (gb != 0)
        if mask.any() and float(np.median(np.abs(ga[mask] - gb[mask]))) > tolerance:
            return 'forma_de_seña'
        # Coherencia temporal: sin saltos mayores que los del original.
        for index in range(2):
            wa = original[:, HANDS[index]][:, :2]
            wb = sample[:, HANDS[index]][:, :2]
            va = np.all(original[:, HANDS[index]][:, :3] != 0, axis=1)
            vb = np.all(sample[:, HANDS[index]][:, :3] != 0, axis=1)
            ok = va[1:] & va[:-1] & vb[1:] & vb[:-1]
            if ok.any():
                ja = np.linalg.norm(np.diff(wa, axis=0), axis=1)[ok]
                jb = np.linalg.norm(np.diff(wb, axis=0), axis=1)[ok]
                if jb.max() > ja.max() * (1.6 + self.level.speed) + .03:
                    return 'saltos_temporales'
        return None


def hand_vector(sequence):
    """Vector compacto (manos relativas a su muñeca) para detectar copias."""
    from recognition_features import local_hands
    local = local_hands(sequence)[:, :126].reshape(-1)
    # La posición y escala de imagen también distinguen escenarios de cámara.
    image = np.concatenate([sequence[:, region].reshape(-1) for region in HANDS])
    return np.concatenate([local, image * 2])


@dataclass
class Result:
    samples: list
    params: list
    rejected: Counter
    attempts: int
    cancelled: bool = False


def generate(source, count, level=DEFAULT_LEVEL, seed=0, static=False, label_text=None,
             semantic_check=None, progress=None, cancelled=None, max_attempts_factor=6, batch=25, scenarios=False):
    """Genera ``count`` variaciones válidas de ``source`` (30, 492).

    ``semantic_check(batch) -> list[bool]`` (opcional) confirma que el modelo
    activo sigue reconociendo la seña; ``progress(done, attempts, rejected)``
    informa avance y ``cancelled()`` permite detener el proceso.
    """
    if level not in LEVELS:
        raise ValueError('Nivel desconocido: usa conservador, equilibrado o avanzado.')
    source = np.asarray(source, np.float32)
    if source.shape != (SEQUENCE_LENGTH, FEATURE_DIM) or not np.isfinite(source).all():
        raise ValueError('La muestra de origen no tiene el formato del dataset (30 × 492).')
    if not any(np.any(source[:, r] != 0) for r in HANDS):
        raise ValueError('La muestra de origen no tiene manos detectadas.')
    config = LEVELS[level]
    confusable = label_is_confusable(label_text)
    validator = Validator(config, confusable)
    rng = np.random.default_rng(seed)
    accepted, params_out, vectors = [], [], [hand_vector(source)]
    rejected = Counter()
    attempts = 0
    limit = max(count * max_attempts_factor, 20)
    while len(accepted) < count and attempts < limit:
        if cancelled and cancelled():
            return Result(accepted, params_out, rejected, attempts, cancelled=True)
        pending = []
        for _ in range(min(batch, count - len(accepted), limit - attempts) or 1):
            attempts += 1
            params = (scenario_params(config, rng, static, confusable, (int(seed) % len(SCENARIOS)) + attempts - 1)
                      if scenarios else sample_params(config, rng, static, confusable))
            sample = apply(source, params)
            reference = time_warp(source, params.speed, params.offset) if (params.speed != 1 or params.offset) else source
            reason = validator.check(source, sample, reference)
            if reason:
                rejected[reason] += 1
                continue
            vector = hand_vector(sample)
            # Copia casi idéntica: diferencia media menor al 0.8 % del tamaño de la palma.
            if min(float(np.sqrt(np.mean((vector - v) ** 2))) for v in vectors) < validator.min_distance:
                rejected['duplicado'] += 1
                continue
            pending.append((sample, params, vector))
        if pending and semantic_check is not None:
            verdicts = semantic_check(np.stack([p[0] for p in pending]))
            kept = []
            for item, ok in zip(pending, verdicts):
                if ok:
                    kept.append(item)
                else:
                    rejected['modelo_no_la_reconoce'] += 1
            pending = kept
        for sample, params, vector in pending:
            if len(accepted) >= count:
                break
            accepted.append(sample)
            params_out.append(params)
            vectors.append(vector)
        if progress:
            progress(len(accepted), attempts, dict(rejected))
    return Result(accepted, params_out, rejected, attempts)


def sample_id(source_digest, params: Params, level):
    raw = json.dumps({'source': source_digest, 'params': params.summary(), 'level': level}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
