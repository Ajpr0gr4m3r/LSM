"""Almacén de muestras sintéticas, separado del dataset real.

Las sintéticas viven en ``web_data/synthetic/<perfil>/<seña>/*.npz`` con el mismo
contrato que las tomas reales (``points``, ``pipeline`` y ``metadata``), pero:

  · nunca se leen al contar ejemplos, auditar ni separar entrenamiento,
    validación y prueba (solo se usan las tomas reales para evaluar);
  · cada una guarda su origen (archivo, huella de la toma de origen,
    transformación, semilla y nivel);
  · al entrenar solo entran si su origen pertenece al conjunto de
    ENTRENAMIENTO (o es una foto/video que no está en ningún conjunto real).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from collections import Counter, defaultdict

import numpy as np

from sign_languages import WEB_DATA, language_info, pipeline_spec, validate_label
from web_dataset import validate_identifier, validate_sequence

MODES = ('real', 'mixed', 'synthetic')


def synthetic_dir(language):
    language_info(language)
    return WEB_DATA / 'synthetic' / language


def digest(points):
    return hashlib.sha256(np.asarray(points, dtype=np.float32).tobytes()).hexdigest()


def save_synthetic(language, label, points, metadata, sample_id=None):
    validate_label(language, label)
    points = validate_sequence(points)
    folder = synthetic_dir(language) / label
    folder.mkdir(parents=True, exist_ok=True)
    identifier = sample_id or uuid.uuid4().hex
    validate_identifier(identifier)
    target = folder / f'{identifier}.npz'
    temp = target.with_suffix('.tmp')
    meta = {**metadata, 'synthetic': True, 'label': label}
    with temp.open('wb') as stream:
        np.savez_compressed(stream, points=points, pipeline=json.dumps(pipeline_spec()),
                            metadata=json.dumps(meta, ensure_ascii=False))
    os.replace(temp, target)
    return target.name


def read_synthetic(path):
    with np.load(path, allow_pickle=False) as data:
        if json.loads(str(data['pipeline'].item())) != pipeline_spec():
            raise ValueError('La muestra sintética pertenece a otra configuración de captura.')
        return validate_sequence(data['points']), json.loads(str(data['metadata'].item()))


def inventory(language):
    root = synthetic_dir(language)
    counts = Counter()
    if root.is_dir():
        for path in root.glob('*/*.npz'):
            counts[path.parent.name] += 1
    return dict(counts)


def with_synthetic_counts(language, real_rows):
    """Vista conjunta del dataset, conservando la procedencia de cada ejemplo."""
    counts = inventory(language)
    return [{**row, 'synthetic_samples': counts.get(row['id'], 0),
             'total_samples': row['samples'] + counts.get(row['id'], 0)} for row in real_rows]


def clear(language, label=None):
    root = synthetic_dir(language)
    target = root / label if label else root
    if label:
        validate_label(language, label)
    removed = sum(1 for _ in target.glob('**/*.npz')) if target.exists() else 0
    if target.exists():
        shutil.rmtree(target)
    return removed


def select_for_training(language, label_ids, train_digests, eval_digests, real_train_counts,
                        mode='mixed', ratio=1., seed=42, max_per_class=600):
    """Elige sintéticas sin fuga: devuelve (puntos, índices de clase, resumen).

    ``train_digests`` / ``eval_digests``: huellas de las tomas reales de
    entrenamiento y de validación+prueba. Una sintética derivada de una toma de
    evaluación se excluye siempre; una derivada de una toma del dataset que no
    quedó en entrenamiento también. Las de fotos/videos que no están en el
    dataset real son independientes de la evaluación y pueden usarse.
    """
    if mode not in MODES:
        raise ValueError('Modo de datos desconocido: usa real, mixed o synthetic.')
    summary = {'mode': mode, 'ratio': ratio, 'used': {}, 'available': {}, 'excluded_leak': 0,
               'excluded_other_source': 0, 'invalid': 0}
    if mode == 'real':
        return np.zeros((0,), np.float32), np.zeros((0,), int), summary
    rng = np.random.default_rng(seed)
    root = synthetic_dir(language)
    points, targets = [], []
    for index, label in enumerate(label_ids):
        candidates = []
        for path in sorted((root / label).glob('*.npz')) if (root / label).is_dir() else []:
            try:
                sequence, meta = read_synthetic(path)
            except (ValueError, OSError, KeyError):
                summary['invalid'] += 1
                continue
            source = meta.get('source_digest')
            if source in eval_digests:
                summary['excluded_leak'] += 1
                continue
            if meta.get('origin') == 'dataset' and source not in train_digests:
                summary['excluded_other_source'] += 1
                continue
            candidates.append(sequence)
        summary['available'][label] = len(candidates)
        if mode == 'mixed':
            limit = int(round(ratio * real_train_counts[index]))
        else:
            limit = max_per_class
        limit = min(limit, max_per_class, len(candidates))
        chosen = rng.choice(len(candidates), size=limit, replace=False) if limit else []
        for i in chosen:
            points.append(candidates[i])
            targets.append(index)
        summary['used'][label] = int(limit)
    summary['total'] = len(points)
    if not points:
        return np.zeros((0,), np.float32), np.zeros((0,), int), summary
    return np.stack(points).astype(np.float32), np.asarray(targets), summary
