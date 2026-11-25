"""Operaciones locales del estudio, con aislamiento por lengua y controles administrativos."""
import json
import numpy as np
import os
from pathlib import Path
import uuid
from datetime import datetime, timezone
import sign_languages as languages
from sign_languages import model_dir, dataset_dir, validate_label, language_info, pipeline_spec
from recognition_features import feature_dimension
from web_dataset import inventory, validate_identifier
from dataset_tools import audit_dataset, export_dataset, import_dataset, sample_rows, inspect_sample


def current_selection(root):
    try:
        selected = json.loads((root / 'current.json').read_text(encoding='utf-8'))
        return selected if isinstance(selected, dict) else {}
    except (OSError, ValueError):
        return {}


# Campos enormes que no hacen falta para listar versiones ni elegir la activa.
HEAVY_METADATA_KEYS = ('posture_vote', 'hand_guard', 'temporal_guard', 'split_hashes', 'split_groups')
# Campos mínimos para decidir qué versión activar al arrancar.
INDEX_KEYS = ('language', 'pipeline', 'preprocessing', 'created_at', 'auto_activate')
INDEX_NAME = '.metadata_index.json'
_SUMMARY_CACHE = {}


def _stamp(path):
    stat = path.stat()
    return [stat.st_size, stat.st_mtime_ns]


def _metadata_summary(path):
    """Lee un metadata.json una sola vez por cambio de archivo y quita los campos pesados."""
    stamp = _stamp(path)
    cached = _SUMMARY_CACHE.get(str(path))
    if cached and cached[0] == stamp:
        return cached[1]
    meta = json.loads(path.read_text(encoding='utf-8'))
    summary = {key: value for key, value in meta.items() if key not in HEAVY_METADATA_KEYS}
    _SUMMARY_CACHE[str(path)] = (stamp, summary)
    return summary


def _light_index(language):
    """Índice pequeño en disco: evita leer cientos de MB de metadatos en cada arranque."""
    root = model_dir(language)
    index_path = root / INDEX_NAME
    try:
        stored = json.loads(index_path.read_text(encoding='utf-8'))
        stored = stored if isinstance(stored, dict) else {}
    except (OSError, ValueError):
        stored = {}
    index, changed = {}, False
    for path in root.glob('*/metadata.json'):
        version = path.parent.name
        try:
            validate_identifier(version)
            stamp = _stamp(path)
        except (ValueError, OSError):
            continue
        entry = stored.get(version)
        if not isinstance(entry, dict) or entry.get('stamp') != stamp:
            try:
                meta = _metadata_summary(path)
            except (ValueError, OSError):
                continue
            entry = {key: meta.get(key) for key in INDEX_KEYS}
            entry.update(stamp=stamp, label_count=len(meta.get('labels') or []))
            changed = True
        index[version] = entry
    if changed or set(index) != set(stored):
        try:
            temporary = root / (INDEX_NAME + '.tmp')
            temporary.write_text(json.dumps(index), encoding='utf-8')
            os.replace(temporary, index_path)
        except OSError:
            pass  # El índice es solo una caché; sin él todo sigue funcionando.
    return index


def compatible_metadata(language, light=False):
    """Lee una versión a la vez y descarta pipelines incompatibles.

    Con ``light=True`` devuelve solo los campos del índice (rápido, para el arranque)."""
    root = model_dir(language)
    if light:
        for version, meta in _light_index(language).items():
            try:
                if meta['language'] != language or meta['pipeline'] != pipeline_spec():
                    continue
                feature_dimension(meta.get('preprocessing'))
                yield version, meta, meta['stamp'][1] / 1e9
            except (ValueError, KeyError, TypeError):
                continue
        return
    for path in root.glob('*/metadata.json'):
        try:
            version = path.parent.name
            validate_identifier(version)
            meta = _metadata_summary(path)
            if meta['language'] != language or meta['pipeline'] != pipeline_spec():
                continue
            feature_dimension(meta.get('preprocessing'))
            yield version, dict(meta), path.stat().st_mtime
        except (ValueError, KeyError, OSError):
            continue


# Lista versiones y diagnósticos para la vista de Entrenamiento.
def versions(language):
    selected = current_selection(model_dir(language))
    result = []
    for version, meta, modified in compatible_metadata(language):
        if meta.get('confusion_matrix') and not meta.get('test_evaluation'):
            from recognition_analysis import confusion_analysis
            meta['legacy_confusions'] = confusion_analysis(meta['confusion_matrix'], meta['labels'])
        summary = {k: v for k, v in meta.items() if k not in HEAVY_METADATA_KEYS}
        active = selected.get('version') == version and not selected.get('requires_retraining')
        result.append((modified, dict(summary, version=version, active=active)))
    return [row for _, row in sorted(result, key=lambda item: item[0], reverse=True)]


def load_inference_model(path):
    """Carga todos los pesos del modelo y da un diagnóstico de compatibilidad."""
    from importlib.metadata import version
    import tensorflow as tf
    import keras_portability

    # Los modelos entrenados en Mac/Linux guardan rutas con «/»; Windows las busca con «\\».
    keras_portability.install()
    try:
        model = tf.keras.models.load_model(path, compile=False, safe_mode=True)
    except ValueError as error:
        message = str(error)
        if 'expected ' not in message or 'received 0 variables' not in message:
            raise
        python = r'.\.venv\Scripts\python.exe' if os.name == 'nt' else '.venv/bin/python'
        raise ValueError(
            f'No se pudieron cargar todos los pesos del modelo {path.parent.name} '
            f'con TensorFlow {tf.__version__} y Keras {version("keras")}. '
            f'En la carpeta LSM ejecuta {python} -m pip install -r requirements.txt '
            'y reinicia Seña. Si ya usas esas versiones, verifica que el archivo model.keras '
            'coincida con el del repositorio.'
        ) from error
    # Grafo compilado una sola vez: misma operación que model(x), pero sin los
    # ~5 ms de sobrecarga de Keras en cada fotograma.
    try:
        spec = tf.TensorSpec([None] + list(model.input_shape[1:]), tf.float32)
        model.sena_predict = tf.function(lambda batch: model(batch, training=False), input_signature=[spec])
    except (AttributeError, TypeError, ValueError):
        pass  # sin grafo compilado se usa model(x), con el mismo resultado
    return model


def predict(model, batch):
    """Probabilidades del modelo para un lote (usa el grafo compilado si existe)."""
    batch = np.asarray(batch, dtype=np.float32)
    fast = getattr(model, 'sena_predict', None)
    return (fast(batch) if fast is not None else model(batch, training=False)).numpy()


# Valida vocabulario, archivos y dimensiones antes de cambiar atómicamente la versión activa.
def activate_version(language, version):
    validate_identifier(version)
    root=model_dir(language)
    metadata=json.loads((root/version/'metadata.json').read_text(encoding='utf-8'))
    if metadata['language']!=language or metadata['pipeline']!=pipeline_spec():
        raise ValueError('El modelo pertenece a otra lengua o configuración.')
    feature_dimension(metadata.get('preprocessing'))
    if not (root/version/'model.keras').is_file() or len(metadata['labels'])<2:
        raise ValueError('La versión está incompleta.')
    counts={r['id']:r['samples'] for r in inventory(language)}
    if any(counts.get(r['id'],0)<languages.MIN_SAMPLES for r in metadata['labels']):
        raise ValueError('Esta versión incluye señas eliminadas o con menos de 30 ejemplos. Reúne los ejemplos y reentrena.')
    # Comprobar dimensiones y serialización antes de tocar el puntero activo.
    model = load_inference_model(root / version / 'model.keras')
    expected=(pipeline_spec()['sequence_length'],feature_dimension(metadata.get('preprocessing')))
    if tuple(model.input_shape[1:])!=expected or model.output_shape[-1]!=len(metadata['labels']):
        raise ValueError('Dimensiones incompatibles con los metadatos.')
    temporary=root/'current.tmp'
    temporary.write_text(json.dumps({'version':version}))
    os.replace(temporary,root/'current.json')
    return {'activated':True,'version':version}


def activate_latest_version(language):
    """Selecciona el último modelo completo y compatible por fecha de entrenamiento."""
    root = model_dir(language)
    selection = current_selection(root)
    compatible = list(compatible_metadata(language, light=True))
    chosen = selection.get('version')
    # Respetar la versión elegida (al entrenar o a mano en Entrenamiento) mientras
    # siga completa y compatible. Antes, el arranque activaba siempre la más
    # reciente y deshacía cualquier activación manual de una versión anterior.
    if (chosen and not selection.get('requires_retraining') and (root / chosen / 'model.keras').is_file()
            and any(version == chosen and meta.get('label_count', 0) >= 2 for version, meta, _ in compatible)):
        return chosen
    candidates = [
        (meta.get('created_at') or '', modified, version)
        for version, meta, modified in compatible
        if meta.get('auto_activate') is not False and meta.get('label_count', 0) >= 2
        and (root / version / 'model.keras').is_file()
    ]
    for _, _, version in sorted(candidates, reverse=True):
        # El modelo que ya está activo se validó al activarlo. Las operaciones
        # de borrado que lo invalidan marcan el manifiesto para reentrenar.
        if version == selection.get('version') and not selection.get('requires_retraining'):
            return version
        try:
            activate_version(language, version)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        return version
    return None


_ACTIVITY_CACHE = (None, [])


# Resume trabajos y operaciones recientes usando una caché basada en archivos modificados.
def recent_activity():
    global _ACTIVITY_CACHE
    jobs=sorted((languages.WEB_DATA/'jobs').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:8]
    deletions=sorted((languages.WEB_DATA/'trash').glob('*/*/deletion.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:8]
    files=jobs+deletions
    key=tuple((str(p),p.stat().st_mtime_ns) for p in files)
    if _ACTIVITY_CACHE[0]==key:
        return _ACTIVITY_CACHE[1]
    result=[]
    for p in files:
        try:
            record=json.loads(p.read_text(encoding='utf-8'))
            result.append({'kind':'training' if p in jobs else 'deletion','time':p.stat().st_mtime,
                           'language':record.get('language'),'state':record.get('state','archived'),
                           'message':record.get('message',f"{record.get('samples',1)} ejemplos retirados")})
        except (ValueError,OSError):
            continue
    result=sorted(result,key=lambda r:r['time'],reverse=True)[:10]
    _ACTIVITY_CACHE=key,result
    return result


# Enruta auditoría, importación, exportación y cambios administrativos dentro de una sola lengua.
def dataset_operation(runtime, route, payload):
    language=payload.get('language')
    language_info(language)
    if route=='/api/dataset/audit':
        return audit_dataset(language)
    if route=='/api/dataset/sample':
        return inspect_sample(language,payload.get('sample'))
    if route=='/api/dataset/export':
        return export_dataset(language)
    if route=='/api/dataset/import':
        if runtime.training() or any(s.capture for s in runtime.sessions.values()):
            raise ValueError('Termina las capturas y el entrenamiento antes de importar.')
        return import_dataset(language,payload.get('data'))
    if route not in ('/api/dataset/delete','/api/dataset/move'):
        raise ValueError('Operación de dataset no encontrada.')
    runtime.admin.verify(payload.get('password'))
    if payload.get('confirmed') is not True:
        raise ValueError('Confirma la modificación de ejemplos.')
    if runtime.training() or any(s.capture for s in runtime.sessions.values()):
        raise ValueError('Termina las capturas y el entrenamiento antes de modificar ejemplos.')
    selected=payload.get('samples')
    if not isinstance(selected,list) or not selected or len(selected)>2000:
        raise ValueError('Selecciona de 1 a 2000 ejemplos.')
    rows={r['id']:r for r in sample_rows(language)}
    if len(set(selected))!=len(selected) or any(not isinstance(key,str) or key not in rows for key in selected):
        raise ValueError('La selección de ejemplos no es válida.')
    if route.endswith('/move'):
        target=payload.get('target')
        validate_label(language,target)
        for key in selected:
            destination=dataset_dir(language)/target/f'{key}.npz'
            if destination.exists() and rows[key]['label']!=target:
                raise ValueError('Ya existe un ejemplo con ese identificador en el destino.')
    for key in selected:
        source=dataset_dir(language)/rows[key]['label']/f'{key}.npz'
        if not source.is_file() or source.is_symlink() or source.parent.is_symlink():
            raise ValueError('La selección cambió o contiene enlaces no permitidos. Vuelve a analizar el dataset.')
    # Invalidar cada clase afectada antes de modificar sus archivos.
    affected={rows[key]['label'] for key in selected}
    if route.endswith('/move'):
        affected.add(target)
    for label in affected:
        runtime.invalidate_label_model(language,label)
    receipt=languages.WEB_DATA/'trash'/language/uuid.uuid4().hex
    receipt.mkdir(parents=True,exist_ok=False)
    (receipt/'deletion.json').write_text(json.dumps({'language':language,'samples':len(selected),
        'operation':route.rsplit('/',1)[-1],'ids':selected,'original_labels':{key:rows[key]['label'] for key in selected},'deleted_at':datetime.now(timezone.utc).isoformat()},ensure_ascii=False))
    moved=[]
    try:
        for key in selected:
            row=rows[key];source=dataset_dir(language)/row['label']/f'{key}.npz'
            destination=(dataset_dir(language)/target if route.endswith('/move') else receipt/row['label'])/source.name
            destination.parent.mkdir(parents=True,exist_ok=True)
            os.replace(source,destination)
            moved.append((source,destination))
    except Exception:
        for source,destination in reversed(moved):
            os.replace(destination,source)
        raise
    return {'changed':len(selected),'recoverable':route.endswith('/delete')}
