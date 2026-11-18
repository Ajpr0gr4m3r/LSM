"""Reproduce tomas grabadas como si llegaran de la cámara y mide la confirmación.

Usa exactamente ``Runtime.recognize`` (el mismo código que la cámara, después de
MediaPipe). Para cada toma del conjunto de prueba del modelo activo simula:
la seña completa y luego la misma seña sostenida otros ``--hold`` fotogramas.

Ejemplo:
    python tools/replay_recognition.py --fps 10 --hold 30
    python tools/replay_recognition.py --split validation --json reporte.json
"""
import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402


def load_split(metadata, split, language, limit):
    from dataset_tools import digest
    from web_dataset import dataset_dir, load_sequence
    wanted = set((metadata.get('split_hashes') or {}).get(split) or [])
    by_id = {label['id']: label for label in metadata['labels']}
    rows = []
    for path in sorted(dataset_dir(language).glob('*/*.npz')):
        label = by_id.get(path.parent.name)
        if label is None:
            continue
        try:
            points = load_sequence(path)
        except ValueError:
            continue
        if wanted and digest(points) not in wanted:
            continue
        rows.append((label, points))
    if limit:
        per = collections.defaultdict(list)
        for row in rows:
            per[row[0]['id']].append(row)
        rows = [r for items in per.values() for r in items[:limit]]
    return rows


def replay(runtime, session_class, label, points, fps, hold):
    session = session_class(runtime_language)
    stream = list(points) + [points[-1 - (i % 10)] for i in range(hold)]  # seña + postura sostenida
    # Perfil de frases: cada fotograma guardado representa «stride» fotogramas de cámara.
    stream = [frame for frame in stream for _ in range(session.stride)]
    clock = 1000.0
    events = {'first_confirm': None, 'confirmed': None, 'wrong': None, 'codes': collections.Counter(),
              'accepted_windows': 0, 'windows': 0, 'ms': []}
    for index, frame in enumerate(stream):
        clock += 1 / fps
        output = {'confidence': 0, 'stability': 0, 'candidate': None, 'confirmed': None,
                  'rejection_reason': None, 'rejection_code': None}
        hands = bool(np.any(frame[-126:]))
        started = time.perf_counter()
        result = runtime.recognize(session, frame, hands, {'usable': True, 'message': ''}, output, clock,
                                   {'mode': 'test'})
        elapsed = (time.perf_counter() - started) * 1000
        if result.get('inference_skipped') or result.get('candidate') is None and not result.get('rejection_code'):
            continue
        events['windows'] += 1
        events['ms'].append(elapsed)
        if result.get('rejection_code') and not result.get('candidate'):
            events['codes'][result['rejection_code']] += 1
        if result.get('candidate'):
            events['accepted_windows'] += 1
        if result.get('confirmed') and events['first_confirm'] is None:
            events['first_confirm'] = index + 1
            events['confirmed'] = result['confirmed']['id']
            events['wrong'] = result['confirmed']['id'] != label['id']
    return events


def main():
    global runtime_language
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--language', default='lsm')
    parser.add_argument('--split', default='test', choices=['train', 'validation', 'test'])
    parser.add_argument('--fps', type=float, default=10.0, help='Fotogramas procesados por segundo simulados')
    parser.add_argument('--hold', type=int, default=30, help='Fotogramas extra con la seña sostenida')
    parser.add_argument('--limit', type=int, default=0, help='Máximo de tomas por clase (0 = todas)')
    parser.add_argument('--json', help='Guarda el reporte detallado en este archivo')
    parser.add_argument('--version', help='Versión a probar (por defecto, la activa). No cambia el modelo activo.')
    args = parser.parse_args()
    runtime_language = args.language

    import web_app
    from studio_services import model_dir
    runtime = web_app.RUNTIME
    manifest = model_dir(args.language) / 'current.json'
    original = manifest.read_text()
    if args.version:
        # Solo durante la carga: se restaura enseguida para no cambiar el modelo activo.
        manifest.write_text(json.dumps({**json.loads(original), 'version': args.version}))
    try:
        bundle = runtime.load_model(args.language)
    finally:
        manifest.write_text(original)
    # Fijar el modelo cargado: si no, recognize() volvería a leer current.json.
    runtime.load_model = lambda language: bundle
    if not bundle:
        sys.exit('No hay modelo activo.')
    _, metadata = bundle
    rows = load_split(metadata, args.split, args.language, args.limit)
    version = args.version or json.loads(original).get('version')
    print(f'Modelo {version} · {len(rows)} tomas de {args.split} · {args.fps:g} fps · '
          f'{args.hold} fotogramas sostenidos\n')

    per_class = collections.defaultdict(lambda: {'n': 0, 'ok': 0, 'wrong': 0, 'none': 0, 'frames': [],
                                                 'codes': collections.Counter(), 'acc': 0, 'win': 0})
    all_ms = []
    for label, points in rows:
        events = replay(runtime, web_app.Session, label, points, args.fps, args.hold)
        row = per_class[label['text']]
        row['n'] += 1
        row['codes'].update(events['codes'])
        row['acc'] += events['accepted_windows']
        row['win'] += events['windows']
        all_ms.extend(events['ms'])
        if events['confirmed'] is None:
            row['none'] += 1
        elif events['wrong']:
            row['wrong'] += 1
        else:
            row['ok'] += 1
            row['frames'].append(events['first_confirm'])

    print(f'{"Seña":<10} {"tomas":>5} {"bien":>5} {"mal":>4} {"nunca":>5} {"seg. a confirmar":>17}  '
          f'{"ventanas aceptadas":>18}  rechazo más común')
    report = {}
    totals = collections.Counter()
    for text in sorted(per_class):
        row = per_class[text]
        seconds = np.median(row['frames']) / args.fps if row['frames'] else float('nan')
        common = row['codes'].most_common(1)
        accepted = row['acc'] / row['win'] if row['win'] else 0
        print(f'{text:<10} {row["n"]:>5} {row["ok"]:>5} {row["wrong"]:>4} {row["none"]:>5} {seconds:>17.1f}  '
              f'{accepted:>17.0%}  {common[0][0] + " (" + str(common[0][1]) + ")" if common else "—"}')
        totals.update(n=row['n'], ok=row['ok'], wrong=row['wrong'], none=row['none'])
        report[text] = {**{k: v for k, v in row.items() if k != 'codes'}, 'codes': dict(row['codes']),
                        'median_seconds': None if np.isnan(seconds) else seconds}
    n = totals['n'] or 1
    print(f'\nTotal: {totals["ok"]}/{totals["n"]} confirmadas bien ({totals["ok"] / n:.0%}), '
          f'{totals["wrong"]} mal ({totals["wrong"] / n:.0%}), {totals["none"]} nunca ({totals["none"] / n:.0%}).')
    if all_ms:
        print(f'Tiempo de cómputo por fotograma (sin MediaPipe): mediana {np.median(all_ms):.0f} ms, '
              f'p90 {np.percentile(all_ms, 90):.0f} ms.')
    if args.json:
        Path(args.json).write_text(json.dumps({'args': vars(args), 'classes': report, 'totals': dict(totals)},
                                              ensure_ascii=False, indent=1))


runtime_language = 'lsm'
if __name__ == '__main__':
    main()
