"""Catálogo de palabras y frases: registro idempotente y reglas coherentes."""
import sys
import tempfile
import unittest
import unicodedata
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sign_languages as langs
import vocabulary_catalog as catalog


def key(text):
    text = unicodedata.normalize('NFD', text.casefold().replace('ñ', '\0'))
    return ''.join(c for c in text if not unicodedata.combining(c)).replace('\0', 'ñ').strip('¿?¡!.,')


class VocabularyCatalogTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.patch = patch.object(langs, 'WEB_DATA', Path(self.folder.name))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.folder.cleanup()

    def test_entries_are_unique_valid_names(self):
        texts = [text for category in catalog.CATEGORIES for text in category['entries']]
        self.assertGreaterEqual(len(texts), 150)
        self.assertEqual(len(texts), len({key(t) for t in texts}), 'Hay entradas repetidas entre categorías')
        for text in texts:
            self.assertEqual(langs.clean_sign_name(text), text)
        self.assertIn('frases', {c['id'] for c in catalog.CATEGORIES})

    def test_rules_and_grammar_only_use_catalog_words(self):
        known = {key(t) for c in catalog.CATEGORIES for t in c['entries']}
        for rule in catalog.PHRASE_RULES:
            for sign in rule['signs']:
                self.assertIn(key(sign), known, f'{sign} no está en el catálogo')
        verbs = {key(t) for t in next(c for c in catalog.CATEGORIES if c['id'] == 'verbos')['entries']}
        self.assertEqual(verbs, {key(v) for v in catalog.CONJUGATIONS})
        for forms in catalog.CONJUGATIONS.values():
            self.assertEqual(len(forms), 5)
        for word in list(catalog.PRONOUNS) + catalog.QUESTION_WORDS + list(catalog.ARTICLES):
            self.assertIn(key(word), known, word)
        for copula in catalog.COPULAS.values():
            self.assertEqual(len(copula['forms']), 5)
            for word in copula['words']:
                self.assertIn(key(word), known, word)

    def test_add_category_is_idempotent_and_reuses_default_labels(self):
        before = {row['id'] for row in langs.labels_for('lsm')}
        result = catalog.add_category('lsm', 'saludos')
        self.assertEqual(result['total'], len(catalog.CATEGORIES[0]['entries']))
        # «Hola», «Gracias», «Por favor»… ya existen como etiquetas predeterminadas.
        self.assertLess(result['added'], result['total'])
        texts = [row['text'] for row in langs.labels_for('lsm')]
        self.assertEqual(texts.count('Hola'), 1)
        self.assertIn('hola', before)
        self.assertEqual(catalog.add_category('lsm', 'saludos')['added'], 0)
        with self.assertRaises(ValueError):
            catalog.add_category('lsm', 'inexistente')

    def test_status_reports_samples_and_training(self):
        catalog.add_category('lsm', 'frases')
        rows = [{**row, 'samples': 31 if row['text'] == 'Tengo sed' else 0} for row in langs.labels_for('lsm')]
        sed = next(row for row in rows if row['text'] == 'Tengo sed')
        status = catalog.catalog_status('lsm', rows, {'labels': [{'id': sed['id']}]})
        entry = next(e for c in status if c['id'] == 'frases' for e in c['entries'] if e['text'] == 'Tengo sed')
        self.assertEqual((entry['label_id'], entry['samples'], entry['trained']), (sed['id'], 31, True))
        missing = next(e for c in status if c['id'] == 'numeros' for e in c['entries'] if e['text'] == 'Dos')
        self.assertEqual((missing['label_id'], missing['samples'], missing['trained']), (None, 0, False))


if __name__ == '__main__':
    unittest.main()
