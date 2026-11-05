"""Shared, versioned recognition decisions for calibration, evaluation and live use.

Geometry is evidence of novelty, not a second mandatory static classifier.
New policies jointly calibrate its gates with the temporal network on held-out
calibration data. Historical policies keep their original decisions.
"""
import numpy as np

from recognition_analysis import accepted_mask
from recognition_features import (hand_descriptor, temporal_descriptor, nearest_distance,
                                  hand_guard_accept, temporal_guard_accept, temporal_guard_score, regions)



# Mide distancia de forma, rival y trayectoria de una predicción respecto a sus referencias aprendidas.
def evidence(points, predicted, metadata, confidence=0.):
    hand = metadata.get('hand_guard')
    temporal = metadata.get('temporal_guard')
    result = {'hand': 0., 'rival': 0., 'temporal': 0.}
    if hand:
        contrastive = hand.get('version') == 'finger-contrast-v2'
        descriptor = hand_descriptor(points, contrastive, hand.get('descriptor_version'))
        own = hand['classes'][int(predicted)]
        distance = nearest_distance(descriptor, own['references'])
        result['hand'] = distance / max(float(own['max_distance']), 1e-8)
        if contrastive and len(hand['classes']) > 1:
            rival = min(nearest_distance(descriptor, item['references'])
                        for i, item in enumerate(hand['classes']) if i != predicted)
            result['rival'] = distance / max(rival, 1e-8)
        # Si la transición domina el resumen completo, verificar la postura
        # más reciente con las mismas referencias y exigir separación del rival.
        classes = (temporal or {}).get('classes', [])
        if (confidence >= .98 and contrastive and len(hand['classes']) > 1
                and classes and classes[predicted].get('motion_required') is False
                and (result['hand'] > 1. or result['rival'] > (own.get('max_rival_ratio') or .98))):
            tail = points[len(points)//2:]
            recent = hand_descriptor(tail, True, hand.get('descriptor_version'))
            distances = [nearest_distance(recent, item['references']) for item in hand['classes']]
            tail_distance = distances[predicted]
            competitor = min(d for j,d in enumerate(distances) if j != predicted)
            ratio = tail_distance / max(competitor, 1e-8)
            if tail_distance <= own['max_distance'] and ratio <= min(.9, own.get('max_rival_ratio') or .9):
                result['hand'] = tail_distance / max(own['max_distance'], 1e-8)
                result['rival'] = ratio
    if temporal:
        allow_held = confidence >= .98 and result['hand'] <= 1.
        result['temporal'] = temporal_guard_score(points, predicted, temporal, allow_held=allow_held)
    return result


# Calcula las evidencias geométricas de todas las secuencias evaluadas.
def batch_evidence(points, probabilities, metadata):
    rows = [evidence(p, int(i), metadata, float(probabilities[j,i])) for j, (p, i) in enumerate(zip(points, np.argmax(probabilities, axis=1)))]
    return {key: np.array([row[key] for row in rows]) for key in ('hand', 'rival', 'temporal')}


# Construye máscaras separadas de forma, rival, trayectoria y confianza según la política guardada.
def gate_masks(probabilities, policy, scores, strict=False):
    p = np.atleast_2d(probabilities)
    classes = [policy.get('classes', {}).get(str(int(i)), {}) for i in p.argmax(axis=1)]
    hand = np.array([r.get('max_hand_ratio', 1.) for r in classes])
    temporal = np.array([r.get('max_temporal_ratio', 1.) for r in classes])
    rival = np.array([r.get('max_rival_ratio') if r.get('max_rival_ratio') is not None else np.inf for r in classes])
    return {'hand': scores['hand'] <= hand, 'rival': scores['rival'] <= rival,
            'temporal': scores['temporal'] <= temporal,
            'confidence': accepted_mask(p, policy, strict=strict)}


# Combina los filtros geométricos para usarlos también durante la evaluación fuera de cámara.
def policy_allowed(probabilities, policy, scores):
    gates = gate_masks(probabilities, policy, scores)
    return gates['hand'] & gates['rival'] & gates['temporal']


# Ajusta conjuntamente los filtros por clase para maximizar cobertura con precisión empírica suficiente.
def calibrate_joint_policy(probabilities, targets, scores, hand_guard=None, groups=None, motion_guard=None):
    """Maximize observed coverage subject to >=95% precision, >=3 accepted.

    This is an empirical calibration target, NOT a guarantee of 95% precision.
    Its independent evaluation and uncertainty must be reported separately.
    The absolute shape guard is always retained. A static rival veto is only
    retained when it is useful jointly with the actual network predictions.
    """
    p = np.asarray(probabilities); y = np.asarray(targets)
    predicted = p.argmax(axis=1)
    ordered = np.sort(p, axis=1)
    confidence, margin = ordered[:, -1], ordered[:, -1] - ordered[:, -2]
    policy = {'version': 2, 'threshold': 1.01, 'margin': 1.01, 'classes': {},
              'source': 'calibration', 'target_precision': .95, 'minimum_accepted': 3,
              'note': 'Objetivo empírico de calibración; no garantiza esa precisión en uso real.'}
    for i in range(p.shape[1]):
        rival_limit = None
        if (hand_guard or {}).get('version') == 'finger-contrast-v2':
            rival_limit = hand_guard['classes'][i].get('max_rival_ratio')
        # When calibrated trajectory rivals distinguish motion from stillness,
        # a static shape vote must not veto the same distinction again.
        if motion_guard and motion_guard['classes'][i].get('motion_required') and motion_guard['classes'][i].get('rival_classes'):
            rival_limit = None
        best = None
        for limit in list(dict.fromkeys([rival_limit, None])):
            for temporal in (1., 1.25):
                allowed = ((predicted == i) & (scores['hand'] <= 1.) &
                           (scores['temporal'] <= temporal))
                if limit is not None: allowed &= scores['rival'] <= limit
                for threshold in (.4, .5, .6, .7, .8, .85, .9, .95, .98):
                    for delta in (.05, .1, .15, .25, .4):
                        selected = allowed & (confidence >= threshold) & (margin >= delta)
                        count = int(selected.sum()); correct = int(np.sum(y[selected] == i))
                        if count < 3 or correct / count < .95: continue
                        # Keep the original geometry limits on ties; do not
                        # choose higher confidence/margin without evidence.
                        rank = (correct, correct/count, -temporal, limit is not None, -threshold, -delta)
                        if best is None or rank > best[0]:
                            best = (rank, dict(threshold=threshold, margin=delta,
                                max_hand_ratio=1., max_temporal_ratio=temporal, max_rival_ratio=limit,
                                calibration_accepted=count, calibration_correct=correct,
                                calibration_groups=len(set(np.asarray(groups)[selected])) if groups is not None else None,
                                supported=True))
        row = best[1] if best else dict(threshold=1.01, margin=1.01, supported=False,
                calibration_accepted=0, calibration_correct=0, calibration_groups=0,
                max_hand_ratio=1., max_temporal_ratio=1., max_rival_ratio=rival_limit)
        row['support'] = int(np.sum(y == i))
        row['raw_correct'] = int(np.sum((y == i) & (predicted == i)))
        row['reason'] = None if best else ('El modelo no acertó esta clase en calibración.' if row['raw_correct'] == 0 else
                                         'Faltan aciertos fiables en calibración para confirmar esta clase.')
        row['limited_support'] = row['calibration_accepted'] < 10 or (row['calibration_groups'] or 0) < 2
        policy['classes'][str(i)] = row
    return policy


# Describe en qué etapa se rechazan secuencias y qué clases carecen de soporte fiable.
def rejection_report(probabilities, targets, labels, policy, scores):
    p = np.asarray(probabilities); correct = p.argmax(axis=1) == np.asarray(targets)
    masks = gate_masks(p, policy, scores); accepted = np.ones(len(p), bool)
    stages = []
    for name in ('network', 'hand', 'rival', 'temporal', 'confidence'):
        if name != 'network': accepted &= masks[name]
        stages.append(dict(name=name, evaluated=len(p), accepted=int(accepted.sum()),
            correct_accepted=int((accepted & correct).sum()), false_accepts=int((accepted & ~correct).sum()),
            correct_rejected=int((~accepted & correct).sum()), coverage=float(accepted.mean())))
    return {'stages': stages,
            'unsupported_labels': [label['text'] for i, label in enumerate(labels)
                                   if not policy['classes'][str(i)]['supported']],
            'policy_class_support': [{**label, **policy['classes'][str(i)],
                                      'accepted': policy['classes'][str(i)]['calibration_accepted']}
                                     for i, label in enumerate(labels)],
            'note': 'Descartes acumulados de secuencias conocidas; no mide falsos positivos de señas desconocidas.'}


# Aplica la política versionada y devuelve aceptación o una razón concreta de rechazo.
def decision_details(points, probabilities, metadata, strict=False, test_mode=False):
    p = np.asarray(probabilities); index = int(p.argmax())
    policy = metadata.get('decision_policy') or {'threshold': metadata.get('decision_threshold', .85),
                                                'margin': metadata.get('decision_margin', .15)}
    row = policy.get('classes', {}).get(str(index), {})
    if row.get('supported') is False:
        return dict(accepted=False, code='unsupported_class',
                    reason='Esta clase se confunde con otras en validación. El porcentaje mostrado no basta para confirmarla. Revisa sus ejemplos y añade nuevas sesiones.')
    # In test mode, a very high calibrated score may use the agreed 90%
    # acceptance floor. Shape, motion and ambiguity checks still apply.
    if test_mode and not strict and float(p[index]) >= .90 - 1e-7:
        policy = {**policy, 'classes': {**policy.get('classes', {}), str(index):
            {**row, 'threshold': min(float(row.get('threshold', policy.get('threshold', .85))), .90 - 1e-7)}}}
    if policy.get('version') == 2:
        scores = {k: np.array([v]) for k, v in evidence(points, index, metadata, float(p[index])).items()}
        gates = gate_masks(p, policy, scores, strict)
        temporal_classes = (metadata.get('temporal_guard') or {}).get('classes', [])
        static_pose = bool(temporal_classes and temporal_classes[index].get('motion_required') is False)
        temporal_message = ('La secuencia se aleja de las tomas aprendidas. Mantén la postura estable.'
                            if static_pose else 'El movimiento no coincide con los ejemplos. Repite el gesto completo.')
        checks = [('hand', 'Forma de la mano fuera de los ejemplos aprendidos.'),
                  ('rival', 'La forma se parece a otra seña. Repite el gesto completo.'),
                  ('temporal', temporal_message),
                  ('confidence', 'Evidencia insuficiente o seña ambigua. Mantén el gesto o vuelve a empezar.')]
        for key, message in checks:
            if not gates[key][0]: return dict(accepted=False, code=key, reason=message)
        return dict(accepted=True, code=None, reason=None)
    # Preserve historical model behavior, with a more specific explanation.
    if not hand_guard_accept(points, index, metadata.get('hand_guard')):
        return dict(accepted=False, code='hand', reason='La forma se aleja de los ejemplos aprendidos. Añade tomas variadas.')
    if not temporal_guard_accept(points, index, metadata.get('temporal_guard')):
        return dict(accepted=False, code='temporal', reason='El movimiento no coincide con los ejemplos aprendidos.')
    accepted = bool(accepted_mask(p, policy, strict=strict)[0])
    return dict(accepted=accepted, code=None if accepted else 'confidence',
                reason=None if accepted else 'Seña ambigua. Mantén el gesto o vuelve a empezar.')
