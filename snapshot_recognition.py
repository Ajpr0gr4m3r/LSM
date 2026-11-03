"""Experimental single-image hand-shape comparison, separately calibrated.

References come exclusively from the active model's training hand guard.
Only the frozen validation recordings calibrate image decisions. No test data,
new vocabulary, fabricated frames for the temporal network, or image storage.
"""
import numpy as np
from recognition_features import hand_descriptor, nearest_distance


# Extrae únicamente la parte estática del descriptor de mano para comparar una imagen.
def descriptor(frame, guard):
    # Two identical landmark observations only provide the static median of the
    # shared descriptor. This is NOT a temporal-network prediction.
    sequence = np.repeat(np.asarray(frame, np.float32)[None], 2, axis=0)
    full = hand_descriptor(sequence, guard.get('version') == 'finger-contrast-v2', guard.get('descriptor_version'))
    return full[:len(full)//2]


# Calcula la distancia de la postura capturada a las referencias entrenadas de cada clase.
def distances(frame, bundle):
    value = descriptor(frame, bundle['guard'])
    return np.array([nearest_distance(value, refs) for refs in bundle['references']])


# Calibra límites del experimento con la reserva de validación y excluye clases de movimiento.
def build_snapshot(metadata, validation, targets):
    guard = metadata.get('hand_guard')
    labels = metadata['labels']
    if not guard or len(guard['classes']) != len(labels):
        raise ValueError('Este modelo no incluye referencias de manos. Entrena una versión nueva para usar la foto experimental.')
    references = []
    for item in guard['classes']:
        refs = np.asarray(item['references'], np.float32)
        if refs.ndim != 2 or not len(refs) or refs.shape[1] % 2:
            raise ValueError('Referencias de manos incompatibles con el modo de imagen.')
        references.append(refs[:, :refs.shape[1]//2])
    bundle = {'guard': guard, 'references': references, 'labels': labels, 'policies': [],
              'moving': list((metadata.get('motion_profile') or {}).get('moving_classes', []))}
    if metadata.get('motion_profile') is None:
        raise ValueError('Falta el diagnóstico de movimiento del modelo. Entrena una versión nueva antes de usar una sola foto.')
    y = np.asarray(targets, int)
    rows = np.stack([distances(frame, bundle) for frame in validation]) if len(validation) else np.empty((0,len(labels)))
    predicted = rows.argmin(axis=1) if len(rows) else np.array([], int)
    for i in range(len(labels)):
        supported = False; best = None
        if len(rows) and i not in bundle['moving']:
            own = rows[:, i]
            rival = np.delete(rows, i, axis=1).min(axis=1)
            correct_distances = own[(predicted == i) & (y == i)]
            for radius in np.unique(np.quantile(correct_distances, [.5,.75,.9,1.])) if len(correct_distances) else []:
                for ratio in (.6,.75,.85,.9,.98):
                    accepted = (predicted == i) & (own <= max(float(radius),1e-6)) & (own < ratio*rival)
                    n = int(accepted.sum()); correct = int(np.sum(accepted & (y == i)))
                    if n >= 3 and correct/n >= .95:
                        rank = (correct, correct/n, -ratio, -float(radius))
                        if best is None or rank > best[0]:
                            best = (rank, {'radius': max(float(radius),1e-6), 'ratio':ratio, 'accepted':n,'correct':correct})
        if best is not None: supported=True
        bundle['policies'].append({**(best[1] if best else {}), 'supported':supported, 'validation_samples':int(np.sum(y==i))})
    return bundle


# Devuelve una forma confirmada o rechazo por movimiento, soporte insuficiente, distancia o ambigüedad.
def classify_snapshot(frame, bundle):
    scores = distances(frame, bundle)
    order = scores.argsort()
    index = int(order[0]); policy = bundle['policies'][index]
    alternatives = [{**bundle['labels'][int(i)], 'distance': round(float(scores[i]),5)} for i in order[:3]]
    reason = None
    if index in bundle['moving']:
        reason = 'La forma más cercana pertenece a una seña con movimiento. Usa el reconocimiento temporal.'
    elif not policy['supported']:
        reason = 'Esta forma no tiene suficientes aciertos fiables en la validación de fotos.'
    elif scores[index] > policy['radius']:
        reason = 'La mano está fuera de las formas validadas. Revisa los dedos y el encuadre.'
    elif scores[index] >= policy['ratio'] * scores[order[1]]:
        reason = 'La postura se parece a varias señas. La foto no permite confirmarla.'
    return {'accepted': reason is None, 'label': bundle['labels'][index] if reason is None else None,
            'alternatives': alternatives, 'reason':reason,
            'validation_support':policy['validation_samples'],
            'method':'snapshot-hand-shape-v1',
            'note':'Distancia geométrica, no probabilidad del modelo temporal. Solo compara formas de mano; no interpreta movimiento ni gramática.'}
