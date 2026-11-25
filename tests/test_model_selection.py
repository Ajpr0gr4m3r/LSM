"""El arranque respeta la versión elegida y solo usa la más reciente como respaldo."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import studio_services
from recognition_features import CHEST_PREPROCESSING
from sign_languages import pipeline_spec


class StartupSelectionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        for version, created in (('a' * 32, '2026-11-01T00:00:00+00:00'), ('b' * 32, '2026-11-20T00:00:00+00:00')):
            folder = self.root / version
            folder.mkdir()
            (folder / 'model.keras').write_bytes(b'x')
            (folder / 'metadata.json').write_text(json.dumps({
                'language': 'lsm', 'pipeline': pipeline_spec(), 'preprocessing': CHEST_PREPROCESSING,
                'created_at': created, 'labels': [{'id': 'a'}, {'id': 'b'}],
                'auto_activate': version == 'b' * 32}))
        self.patch = patch.object(studio_services, 'model_dir', return_value=self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.root)

    def select(self, manifest):
        (self.root / 'current.json').write_text(json.dumps(manifest))
        with patch.object(studio_services, 'activate_version', side_effect=lambda language, version: {'version': version}) as activate:
            return studio_services.activate_latest_version('lsm'), activate

    def test_manual_choice_of_older_version_survives_restart(self):
        chosen, activate = self.select({'version': 'a' * 32})
        self.assertEqual(chosen, 'a' * 32)
        activate.assert_not_called()

    def test_invalid_or_missing_choice_falls_back_to_newest(self):
        chosen, _ = self.select({'version': 'a' * 32, 'requires_retraining': True})
        self.assertEqual(chosen, 'b' * 32)
        chosen, _ = self.select({'version': 'c' * 32})
        self.assertEqual(chosen, 'b' * 32)
        chosen, _ = self.select({})
        self.assertEqual(chosen, 'b' * 32)


if __name__ == '__main__':
    unittest.main()
