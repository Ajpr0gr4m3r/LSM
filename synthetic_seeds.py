"""Selección de tomas reales de entrenamiento como base de generación."""
import numpy as np

from capture_quality import sequence_quality
from recognition_features import prepare_sequence
from recognition_analysis import temperature_probabilities
from recognition_decision import decision_details
from posture_vote import apply_vote
from synthetic_dataset import digest
from web_dataset import dataset_dir, load_sequence

MIN_PRECISION = .95
MIN_ACCEPTED = 3
MIN_CONFIDENCE = .90


def seed_options(metadata):
    """Expone evidencia de validación por clase, sin usar métricas de prueba."""
    rows = {row['id']: row for row in metadata.get('validation_by_class', [])}
    policy = (metadata.get('decision_policy') or {}).get('classes', {})
    options = []
    for index, label in enumerate(metadata['labels']):
        row = rows.get(label['id'], {})
        precision = row.get('accepted_precision')
        accepted = row.get('accepted', 0)
        if (policy.get(str(index), {}).get('supported') is not True
                or precision is None or precision < MIN_PRECISION or accepted < MIN_ACCEPTED):
            continue
        options.append({'id': label['id'], 'text': label['text'],
                        'precision': precision, 'accepted': accepted,
                        'support': row.get('support', 0)})
    return options


def seed_probabilities(model, metadata, sequences):
    features = np.stack([prepare_sequence(x, metadata.get('preprocessing')) for x in sequences])
    probabilities = temperature_probabilities(model(features, training=False).numpy(),
                                               metadata.get('temperature', 1.))
    return apply_vote(features, probabilities, metadata.get('posture_vote'))


def seed_accepts(sequence, probabilities, metadata, target):
    return (int(np.argmax(probabilities)) == target and probabilities[target] >= MIN_CONFIDENCE
            and decision_details(sequence, probabilities, metadata)['accepted'])


def select_seed(language, label_id, bundle):
    """Busca la mejor toma sin derivar datos de validación, calibración o prueba."""
    model, metadata = bundle
    if label_id not in {row['id'] for row in seed_options(metadata)}:
        raise ValueError('Esta seña no tiene suficiente confirmación y validación para usarla como base.')
    splits = metadata.get('split_hashes') or {}
    training = set(splits.get('train') or [])
    reserved = set(h for name, hashes in splits.items() if name != 'train' for h in hashes)
    eligible = training - reserved
    if not eligible:
        raise ValueError('El modelo no registra tomas de entrenamiento disponibles para generar.')
    target = next(i for i, row in enumerate(metadata['labels']) if row['id'] == label_id)
    best = None
    batch = []

    def evaluate():
        nonlocal best
        probabilities = seed_probabilities(model, metadata, [sequence for _, sequence in batch])
        for (path, sequence), prediction in zip(batch, probabilities):
            if seed_accepts(sequence, prediction, metadata, target):
                confidence = float(prediction[target])
                if best is None or confidence > best[0]:
                    best = (confidence, path, sequence)
        batch.clear()

    for path in sorted((dataset_dir(language) / label_id).glob('*.npz')):
        try:
            sequence = load_sequence(path)
            if digest(sequence) not in eligible or sequence_quality(sequence)['usable_ratio'] < .8:
                continue
        except (OSError, ValueError, KeyError):
            continue
        batch.append((path, sequence))
        if len(batch) == 16:
            evaluate()
    if batch:
        evaluate()
    if best is None:
        raise ValueError('No hay una toma de entrenamiento aceptada con al menos 90 % de confianza. Revisa los ejemplos o graba nuevas tomas.')
    return best
