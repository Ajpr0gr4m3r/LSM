"""Perfil LSM con etiquetas de salida en español y rutas de datos independientes."""
import json
import os
import re
import unicodedata
import uuid
from pathlib import Path
from config import BASE_DIR, ACTIONS, FEATURE_DIM, SEQUENCE_LENGTH, FACE_KEY_INDICES, USE_FULL_FACE

ROOT = Path(BASE_DIR)
WEB_DATA = ROOT / 'web_data'
WEB_MODELS = ROOT / 'models'
MIN_SAMPLES = 30
RECOMMENDED_SAMPLES = 60
CAPTURE_FPS = 10
LANGUAGES = [
    {'id': 'lsm', 'code': 'LSM', 'name': 'Lengua de Señas Mexicana', 'region': 'México', 'written': 'Español', 'locale': 'es-MX'},
]

# Estas son etiquetas de significado; NO son ejemplos ni modelos de las señas.
WORDS = {
    'hola': ['Hola'],
    'gracias': ['Gracias'],
    'por_favor': ['Por favor'],
    'me_llamo': ['Me llamo'],
    'mucho_gusto': ['Mucho gusto'],
    'buenos_dias': ['Buenos días'],
    'adios': ['Adiós'],
    'si': ['Sí'],
    'no': ['No'],
    'ayuda': ['Ayuda'],
}

# Valida el identificador y devuelve los datos del perfil de lengua de señas.
def language_info(language):
    for item in LANGUAGES:
        if item['id'] == language:
            return item
    raise ValueError('Lengua de señas desconocida.')

# Combina las etiquetas predeterminadas en español con el vocabulario personalizado de LSM.
def labels_for(language):
    language_info(language)
    index = next(i for i, item in enumerate(LANGUAGES) if item['id'] == language)
    defaults = [{'id': str(a), 'meaning': str(a).replace('_', ' '),
                 'text': WORDS[str(a)][index] if str(a) in WORDS else str(a).replace('_', ' ')} for a in ACTIONS]
    return defaults + custom_labels(language)

# Rechaza etiquetas que no pertenecen al vocabulario de la lengua seleccionada.
def validate_label(language, label):
    if label not in {item['id'] for item in labels_for(language)}:
        raise ValueError('La seña no pertenece al vocabulario configurado.')
    return label

# Devuelve la carpeta de ejemplos de un perfil validado.
def dataset_dir(language):
    language_info(language)
    return WEB_DATA / 'datasets' / language

# Devuelve la carpeta de versiones de modelos de un perfil validado.
def model_dir(language):
    language_info(language)
    return WEB_MODELS / language

# Describe el contrato de captura necesario para comprobar compatibilidad de datos y modelos.
def pipeline_spec():
    return {'version': 'holistic-web-mirror-v1', 'sequence_length': SEQUENCE_LENGTH,
            'feature_dim': FEATURE_DIM, 'full_face': USE_FULL_FACE,
            'face_indices': FACE_KEY_INDICES, 'mirrored': True, 'target_fps': CAPTURE_FPS}


# Normaliza espacios y Unicode y rechaza nombres vacíos, excesivos o con caracteres de control.
def clean_sign_name(name):
    if not isinstance(name, str):
        raise ValueError('Escribe el nombre o significado de la seña.')
    name = unicodedata.normalize('NFKC', name)
    if any(unicodedata.category(c).startswith('C') for c in name):
        raise ValueError('El nombre contiene caracteres de control no permitidos.')
    name = ' '.join(name.split())
    if not name or len(name) > 80:
        raise ValueError('El nombre debe tener entre 1 y 80 caracteres.')
    return name


# Carga y comprueba las etiquetas personalizadas persistidas para una lengua.
def custom_labels(language):
    language_info(language)
    path = WEB_DATA / 'vocabulary' / f'{language}.json'
    if not path.exists():
        return []
    labels = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(labels, list):
        raise ValueError('El vocabulario guardado tiene un formato inválido.')
    seen = set()
    for item in labels:
        if (not isinstance(item, dict) or not re.fullmatch(r'custom_[0-9a-f]{32}', item.get('id', ''))
                or item['id'] in seen):
            raise ValueError('El vocabulario guardado contiene un identificador inválido.')
        clean_sign_name(item.get('text'))
        clean_sign_name(item.get('meaning'))
        seen.add(item['id'])
    return labels


# Reutiliza una etiqueta equivalente o registra una nueva de forma atómica dentro del perfil.
def register_label(language, name):
    """Añade al catálogo de una lengua; el código Python permanece estable."""
    name = clean_sign_name(name)
    normalized = name.lower()
    for label in labels_for(language):
        if any(clean_sign_name(value).lower() == normalized for value in (label['text'], label['meaning'], label['id'])):
            return label
    label = {'id': 'custom_' + uuid.uuid4().hex, 'text': name, 'meaning': name}
    labels = custom_labels(language) + [label]
    path = WEB_DATA / 'vocabulary' / f'{language}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)
    return label
