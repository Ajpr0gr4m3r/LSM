"""Compara dos versiones del modelo con sus métricas de PRUEBA (tomas reales reservadas).

    python tools/compare_models.py <versión_A> <versión_B> [--names "Solo reales" "Reales + sintéticas"]

Ambas versiones deben haberse entrenado con la misma separación (persistent split)
para que la comparación sea justa; el script lo verifica.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(language, version):
    from studio_services import model_dir
    return json.loads((model_dir(language) / version / 'metadata.json').read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('a')
    parser.add_argument('b')
    parser.add_argument('--language', default='lsm')
    parser.add_argument('--names', nargs=2, default=['A', 'B'])
    parser.add_argument('--json', help='Guarda la comparación en este archivo')
    args = parser.parse_args()
    a, b = load(args.language, args.a), load(args.language, args.b)
    same_test = sorted(a['split_hashes']['test']) == sorted(b['split_hashes']['test'])
    print(f'Mismo conjunto de prueba real: {"sí" if same_test else "NO — la comparación no es válida"} '
          f'({len(a["split_hashes"]["test"])} tomas)\n')
    rows = []
    for key, title in (('accuracy', 'Exactitud (top-1)'), ('macro_f1', 'Macro-F1'),
                       ('accepted_accuracy', 'Exactitud de lo confirmado'), ('coverage', 'Cobertura (confirma)')):
        va, vb = a['test_evaluation'].get(key), b['test_evaluation'].get(key)
        rows.append((title, va, vb))
    width = max(len(n) for n in args.names) + 2
    print(f'{"Métrica (prueba real)":<28}{args.names[0]:>{width}}{args.names[1]:>{width}}   Diferencia')
    for title, va, vb in rows:
        if va is None or vb is None:
            continue
        print(f'{title:<28}{va:>{width}.1%}{vb:>{width}.1%}   {vb - va:+.1%}')
    print(f'\n{"Seña":<12}{"recall " + args.names[0]:>22}{"recall " + args.names[1]:>24}')
    report_a, report_b = a['test_evaluation']['report'], b['test_evaluation']['report']
    per_class = []
    for label in a['labels']:
        ra, rb = report_a.get(label['id'], {}), report_b.get(label['id'], {})
        if not ra:
            continue
        per_class.append({'label': label['text'], 'a': ra.get('recall'), 'b': rb.get('recall'),
                          'support': ra.get('support')})
        print(f'{label["text"]:<12}{ra.get("recall", 0):>22.0%}{rb.get("recall", 0):>24.0%}   (n={int(ra.get("support", 0))})')
    for name, meta in zip(args.names, (a, b)):
        summary = meta.get('synthetic') or {'mode': 'real'}
        print(f'\n{name}: modo {summary.get("mode")}, sintéticas usadas {summary.get("total", 0)}, '
              f'excluidas por fuga {summary.get("excluded_leak", 0)}')
    if args.json:
        Path(args.json).write_text(json.dumps({'same_test': same_test, 'metrics': rows, 'per_class': per_class,
                                               'names': args.names}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
