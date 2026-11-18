"""Hace que los archivos .keras se lean y escriban igual en Windows, macOS y Linux.

Keras 2.15 arma las rutas internas del archivo de pesos (model.weights.h5) con
``tf.io.gfile.join``, que en Windows usa ``\\`` y en macOS/Linux usa ``/``.
Un modelo guardado en una Mac tiene grupos como ``layers/sequential/...``; al
cargarlo en Windows Keras busca ``layers\\sequential\\...``, no encuentra nada y
falla con «expected N variables, but received 0 variables».

``install()`` corrige las dos direcciones:
  · al guardar siempre escribe rutas con ``/`` (formato portátil);
  · al cargar prueba la ruta con ``/`` y con ``\\`` para leer modelos antiguos
    guardados en cualquiera de los dos sistemas.
"""

_INSTALLED = False


def _variants(path):
    yield path
    if '\\' in path:
        yield path.replace('\\', '/')
    if '/' in path:
        yield path.replace('/', '\\')


def install():
    """Aplica el parche una sola vez. Es seguro llamarlo antes de cada carga."""
    global _INSTALLED
    if _INSTALLED:
        return True
    try:
        from keras.src.saving import saving_lib
        store = saving_lib.H5IOStore
    except (ImportError, AttributeError):
        # Otra versión de Keras con un formato distinto: no hay nada que corregir.
        return False

    original_make = store.make

    def make(self, path):
        return original_make(self, path.replace('\\', '/') if path else path)

    def get(self, path):
        if not path:
            return self.h5_file['vars']
        for candidate in _variants(path):
            if candidate in self.h5_file and 'vars' in self.h5_file[candidate]:
                return self.h5_file[candidate]['vars']
        return {}

    store.make = make
    store.get = get
    _INSTALLED = True
    return True
