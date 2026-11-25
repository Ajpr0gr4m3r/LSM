"""Genera sintéticas a partir de las tomas REALES de entrenamiento del dataset.

Solo usa tomas que el modelo activo (o el último split guardado) reservó para
ENTRENAMIENTO: nunca deriva variaciones de validación o prueba.

    python tools/generate_from_dataset.py --per-sample 1 --level equilibrado
    python tools/generate_from_dataset.py --labels A B --per-sample 2 --seed 7
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--language', default='lsm')
    parser.add_argument('--labels', nargs='*', help='Textos de las señas (por defecto, todas las del modelo activo)')
    parser.add_argument('--per-sample', type=int, default=1, help='Variaciones por toma real de entrenamiento')
    parser.add_argument('--level', default='equilibrado', choices=['conservador', 'equilibrado', 'avanzado'])
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--no-semantic', action='store_true', help='No comprobar con el modelo activo')
    args = parser.parse_args()

    import synthetic_generator as generator
    from synthetic_dataset import digest, save_synthetic
    from studio_services import model_dir
    from web_dataset import dataset_dir, load_sequence
    import web_app

    bundle = web_app.RUNTIME.load_model(args.language)
    if not bundle:
        sys.exit('Se necesita un modelo activo para saber qué tomas son de entrenamiento.')
    model, metadata = bundle
    train = set((metadata.get('split_hashes') or {}).get('train') or [])
    if not train:
        sys.exit('El modelo activo no guarda su separación de entrenamiento.')
    labels = metadata['labels']
    if args.labels:
        wanted = {t.casefold() for t in args.labels}
        labels = [l for l in labels if l['text'].casefold() in wanted]
    from recognition_features import prepare_sequence
    preprocessing = metadata.get('preprocessing')
    index_of = {l['id']: i for i, l in enumerate(metadata['labels'])}

    total, rejected = 0, {}
    started = time.time()
    for label in labels:
        made = 0
        for number, path in enumerate(sorted((dataset_dir(args.language) / label['id']).glob('*.npz'))):
            try:
                source = load_sequence(path)
            except ValueError:
                continue
            source_digest = digest(source)
            if source_digest not in train:
                continue  # validación o prueba: jamás se derivan variaciones
            check = None
            if not args.no_semantic:
                target = index_of[label['id']]
                predict = lambda batch: model(np.stack([prepare_sequence(x, preprocessing) for x in batch]),
                                              training=False).numpy().argmax(axis=1)
                if predict(source[None])[0] == target:
                    check = lambda batch, p=predict, t=target: list(p(batch) == t)
            result = generator.generate(source, args.per_sample, args.level, seed=args.seed + number * 7919,
                                        label_text=label['text'], semantic_check=check)
            for key, value in result.rejected.items():
                rejected[key] = rejected.get(key, 0) + value
            for sample, params in zip(result.samples, result.params):
                save_synthetic(args.language, label['id'], sample, {
                    'origin': 'dataset', 'file': path.name, 'source_digest': source_digest,
                    'level': args.level, 'seed': params.seed, 'transform': params.summary(),
                    'label_text': label['text'], 'review': 'automatic', 'semantic_check': bool(check),
                    'created_at': time.time()}, sample_id=generator.sample_id(source_digest, params, args.level))
                made += 1
        total += made
        print(f'{label["text"]:<12} {made:>5} sintéticas', flush=True)
    print(f'\nTotal {total} sintéticas en {time.time() - started:.0f} s. Descartadas: {rejected}')


if __name__ == '__main__':
    main()
