"""Un modelo .keras debe cargar igual en Windows, macOS y Linux (Keras 2.15)."""
import io
import ntpath
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')

try:
    import h5py
    import numpy as np
    import tensorflow as tf
    from keras.src.saving import saving_lib
except ImportError:  # pragma: no cover - entornos sin TensorFlow
    tf = None


def nested_model():
    inputs = tf.keras.Input((5, 3))
    normalized = tf.keras.layers.Normalization(mean=[0., 0., 0.], variance=[1., 1., 1.])(inputs)
    body = tf.keras.Sequential([
        tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(4)),
        tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(3)),
        tf.keras.layers.Dense(2, activation='softmax'),
    ])
    return tf.keras.Model(inputs, body(normalized))


def rewrite_weights_with_backslashes(source, target):
    """Reproduce un archivo guardado en Windows antes de la corrección."""
    with zipfile.ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    original = h5py.File(io.BytesIO(files['model.weights.h5']), 'r')
    buffer = io.BytesIO()
    with h5py.File(buffer, 'w') as rewritten:
        def windows_vars(group):
            # Windows creaba un solo grupo con «\\» en el nombre y dentro «vars».
            group = group.rpartition('/vars')[0] if group != 'vars' else ''
            parent = rewritten.require_group(group.replace('/', '\\')) if group else rewritten
            return parent.require_group('vars')

        def copy(name, item):
            if isinstance(item, h5py.Group) and name.split('/')[-1] == 'vars':
                windows_vars(name)
            elif isinstance(item, h5py.Dataset):
                group, _, leaf = name.rpartition('/')
                windows_vars(group)[leaf] = item[()]
        original.visititems(copy)
    original.close()
    files['model.weights.h5'] = buffer.getvalue()
    with zipfile.ZipFile(target, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)


@unittest.skipIf(tf is None, 'TensorFlow no está instalado')
class KerasPortabilityTests(unittest.TestCase):
    def setUp(self):
        from studio_services import load_inference_model
        self.load = load_inference_model
        self.tmp = Path(tempfile.mkdtemp())
        tf.keras.utils.set_random_seed(3)
        self.sample = np.random.default_rng(1).normal(size=(2, 5, 3)).astype('float32')

    def save(self, name, windows=False):
        import keras_portability
        keras_portability.install()
        model = nested_model()
        path = self.tmp / name
        join = ntpath.join if windows else saving_lib.tf.io.gfile.join
        with mock.patch.object(saving_lib.tf.io.gfile, 'join', join):
            model.save(path)
        return model, path

    def test_mac_model_loads_on_windows(self):
        model, path = self.save('mac.keras')
        with mock.patch.object(saving_lib.tf.io.gfile, 'join', ntpath.join):
            loaded = self.load(path)
        np.testing.assert_allclose(loaded(self.sample).numpy(), model(self.sample).numpy(), rtol=1e-6)

    def test_old_windows_model_loads_on_mac(self):
        model, path = self.save('posix.keras')
        legacy = self.tmp / 'windows-legacy.keras'
        rewrite_weights_with_backslashes(path, legacy)
        loaded = self.load(legacy)
        np.testing.assert_allclose(loaded(self.sample).numpy(), model(self.sample).numpy(), rtol=1e-6)

    def test_windows_saves_portable_paths(self):
        _, path = self.save('windows.keras', windows=True)
        with zipfile.ZipFile(path) as archive, h5py.File(io.BytesIO(archive.read('model.weights.h5')), 'r') as weights:
            names = []
            weights.visit(names.append)
        self.assertTrue(names)
        self.assertFalse([name for name in names if '\\' in name])


if __name__ == '__main__':
    unittest.main()
