"""Selección de tomas reales de entrenamiento como base de generación."""
import numpy as np

from recognition_features import prepare_sequence
from recognition_analysis import temperature_probabilities
from posture_vote import apply_vote
from synthetic_dataset import digest
from web_dataset import dataset_dir, load_sequence

def seed_options(metadata):
    """Ordena las señas por precisión de validación, sin exigir un porcentaje mínimo."""
    rows = {row['id']: row for row in metadata.get('validation_by_class', [])}
    options = []
    for label in metadata['labels']:
        row = rows.get(label['id'], {})
        precision = row.get('accepted_precision')
        if precision is None:
            precision = row.get('precision')
        options.append({'id': label['id'], 'text': label['text'],
                        'precision': precision, 'accepted': row.get('accepted', 0),
                        'support': row.get('support', 0)})
    return sorted(options, key=lambda row: row['precision'] if row['precision'] is not None else -1,
                  reverse=True)


def seed_probabilities(model, metadata, sequences):
    features = np.stack([prepare_sequence(x, metadata.get('preprocessing')) for x in sequences])
    probabilities = temperature_probabilities(model(features, training=False).numpy(),
                                               metadata.get('temperature', 1.))
    return apply_vote(features, probabilities, metadata.get('posture_vote'))


def select_seed(language, label_id, bundle):
    """Busca la mejor toma sin derivar datos de validación, calibración o prueba."""
    model, metadata = bundle
    if label_id not in {row['id'] for row in seed_options(metadata)}:
        raise ValueError('La seña no pertenece al modelo activo.')
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
            confidence = float(prediction[target])
            if np.isfinite(confidence) and (best is None or confidence > best[0]):
                best = (confidence, path, sequence)
        batch.clear()

    for path in sorted((dataset_dir(language) / label_id).glob('*.npz')):
        try:
            sequence = load_sequence(path)
            if digest(sequence) not in eligible:
                continue
        except (OSError, ValueError, KeyError):
            continue
        batch.append((path, sequence))
        if len(batch) == 16:
            evaluate()
    if batch:
        evaluate()
    if best is None:
        raise ValueError('No hay tomas reales de entrenamiento disponibles para esta seña.')
    return best
