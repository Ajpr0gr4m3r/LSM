"""Trabajos del Generador de Dataset Sintético (importar, generar, revisar, guardar).

Todo lo pesado corre en hilos: la página consulta el estado y nunca se congela.
El estado vive en memoria del servidor hasta guardar o descartar.
"""
from __future__ import annotations

import base64
import threading
import time
import uuid
from collections import Counter

import numpy as np

import synthetic_generator as generator
import synthetic_media as media
from synthetic_dataset import digest, save_synthetic
from sign_languages import language_info, labels_for, register_label

MAX_SOURCES = 20
PREVIEW_LIMIT = 24
COUNTS = (50, 100, 250, 500, 1000)


def _compact_frames(sequence, stride=3):
    """Esqueleto ligero para animar en el navegador: manos (x, y) y torso."""
    frames = []
    for frame in sequence[::stride]:
        hands = []
        for region in generator.HANDS:
            hand = frame[region].reshape(21, 3)
            hands.append(np.round(hand[:, :2], 4).tolist() if np.any(hand != 0) else None)
        pose = frame[generator.POSE].reshape(33, 4)
        body = {str(i): np.round(pose[i, :2], 4).tolist() for i in (0, 11, 12, 13, 14, 15, 16) if np.any(pose[i, :2] != 0)}
        frames.append({'hands': hands, 'body': body})
    return frames


class SyntheticStudio:
    def __init__(self):
        self.lock = threading.Lock()
        self.sources = {}
        self.jobs = {}

    # ── Fuentes ─────────────────────────────────────────────────────────────
    def add_source(self, language, name, content_type, encoded, mirror=True):
        language_info(language)
        if not isinstance(encoded, str) or not encoded:
            raise ValueError('El archivo está vacío.')
        kind = media.kind_for(name, content_type or '')
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('El archivo no se pudo leer.') from exc
        with self.lock:
            if len([s for s in self.sources.values() if s['language'] == language]) >= MAX_SOURCES:
                raise ValueError(f'Máximo {MAX_SOURCES} archivos a la vez. Guarda o descarta los anteriores.')
            source_id = uuid.uuid4().hex
            self.sources[source_id] = {'id': source_id, 'language': language, 'name': str(name)[:120],
                                       'kind': kind, 'state': 'processing', 'progress': 0., 'warnings': [],
                                       'error': None, 'cancel': False}
        threading.Thread(target=self._process_source, args=(source_id, data, bool(mirror)), daemon=True).start()
        return self.public_source(self.sources[source_id])

    def _process_source(self, source_id, data, mirror):
        source = self.sources[source_id]
        try:
            if source['kind'] == 'image':
                result = media.image_source(data, source['language'], mirror)
            else:
                suffix = '.' + source['name'].rsplit('.', 1)[-1].lower() if '.' in source['name'] else '.mp4'
                def progress(index, total):
                    source['progress'] = min(.99, index / total) if total else 0.
                result = media.video_source(data, source['language'], suffix, mirror, progress,
                                            cancelled=lambda: source['cancel'])
            source.update(state='ready', progress=1., static=result['static'], sequence=result['sequence'],
                          digest=digest(result['sequence']), warnings=result['warnings'],
                          hands=result['hands'], frames_read=result['frames_read'],
                          frames_with_hands=result['frames_with_hands'],
                          preview=_compact_frames(result['sequence'], 1 if result['static'] else 3)[:1 if result['static'] else 10],
                          motion=generator.motion_extent(result['sequence']))
        except media.MediaError as exc:
            source.update(state='error', error=str(exc))
        except Exception as exc:  # noqa: BLE001 - se informa en la interfaz
            import traceback
            traceback.print_exc()
            source.update(state='error', error=f'No se pudo procesar el archivo: {exc}')

    @staticmethod
    def public_source(source):
        keys = ('id', 'name', 'kind', 'state', 'progress', 'warnings', 'error', 'static', 'hands',
                'frames_read', 'frames_with_hands', 'preview', 'motion')
        return {k: source.get(k) for k in keys}

    def remove_source(self, source_id):
        with self.lock:
            source = self.sources.pop(source_id, None)
        if source:
            source['cancel'] = True
        return {'removed': bool(source)}

    # ── Generación ──────────────────────────────────────────────────────────
    def start(self, language, label_text, source_ids, count, level, seed, semantic_bundle=None):
        language_info(language)
        label_text = str(label_text or '').strip()
        if not label_text:
            raise ValueError('Elige o escribe el nombre de la seña.')
        if not isinstance(count, int) or not 1 <= count <= 1000:
            raise ValueError('Elige entre 1 y 1000 muestras.')
        if level not in generator.LEVELS:
            raise ValueError('Nivel desconocido.')
        seed = int(seed) if str(seed).lstrip('-').isdigit() else 0
        sources = [self.sources.get(i) for i in source_ids or []]
        sources = [s for s in sources if s and s['language'] == language and s['state'] == 'ready']
        if not sources:
            raise ValueError('Sube al menos una foto o un video con manos detectadas.')
        if any(j['state'] == 'running' for j in self.jobs.values()):
            raise ValueError('Ya hay una generación en curso. Espera o cancélala.')
        # Una foto no puede representar una seña con movimiento.
        dynamic = self._label_is_dynamic(language, label_text)
        if dynamic and any(s['static'] for s in sources):
            raise ValueError(f'«{label_text}» tiene movimiento según sus tomas reales: usa un video, no una foto. '
                             'Generar movimiento a partir de una foto cambiaría la seña.')
        job_id = uuid.uuid4().hex
        job = {'id': job_id, 'language': language, 'label': label_text, 'level': level, 'seed': seed,
               'count': count, 'state': 'running', 'done': 0, 'attempts': 0, 'rejected': Counter(),
               'samples': [], 'cancel': False, 'error': None, 'started': time.time(),
               'sources': [s['id'] for s in sources], 'semantic': None}
        self.jobs = {job_id: job}  # un trabajo activo; el anterior sin guardar se descarta
        threading.Thread(target=self._run, args=(job, sources, semantic_bundle), daemon=True).start()
        return self.public_job(job)

    @staticmethod
    def _label_is_dynamic(language, label_text):
        """Seña con movimiento si sus tomas reales recorren más de media palma."""
        from web_dataset import dataset_dir, load_sequence
        label = next((l for l in labels_for(language) if l['text'].casefold() == label_text.casefold()), None)
        if not label:
            return False
        extents = []
        for path in sorted((dataset_dir(language) / label['id']).glob('*.npz'))[:15]:
            try:
                sequence = load_sequence(path)
            except ValueError:
                continue
            hands = [sequence[:, r].reshape(30, 21, 3) for r in generator.HANDS]
            palms = [np.linalg.norm(h[:, 9, :2] - h[:, 0, :2], axis=1) for h in hands]
            palm = np.median(np.concatenate([p[p > 0] for p in palms] or [np.array([.1])])) if any((p > 0).any() for p in palms) else .1
            extents.append(generator.motion_extent(sequence) / max(palm, 1e-3))
        return bool(extents) and float(np.median(extents)) > .8

    def _semantic_check(self, bundle, label_text, source_sequence):
        """Comprueba con el modelo activo que las variaciones siguen siendo la misma seña."""
        if not bundle:
            return None, 'sin modelo activo'
        model, metadata = bundle
        index = next((i for i, l in enumerate(metadata['labels']) if l['text'].casefold() == label_text.casefold()), None)
        if index is None:
            return None, 'la seña no está en el modelo activo'
        from recognition_features import prepare_sequence
        preprocessing = metadata.get('preprocessing')

        def predict(batch):
            features = np.stack([prepare_sequence(x, preprocessing) for x in batch])
            return model(features, training=False).numpy().argmax(axis=1)

        if predict(source_sequence[None])[0] != index:
            return None, 'el modelo activo no reconoce el original como esta seña'
        return (lambda batch: list(predict(batch) == index)), 'activa'

    def _run(self, job, sources, bundle):
        try:
            per_source = [job['count'] // len(sources) + (1 if i < job['count'] % len(sources) else 0)
                          for i in range(len(sources))]
            for position, (source, amount) in enumerate(zip(sources, per_source)):
                if not amount:
                    continue
                check, semantic = self._semantic_check(bundle, job['label'], source['sequence'])
                job['semantic'] = semantic
                base_done = job['done']

                def progress(done, attempts, rejected):
                    job['done'] = base_done + done

                result = generator.generate(
                    source['sequence'], amount, job['level'], seed=job['seed'] + position * 9973,
                    static=source['static'], label_text=job['label'], semantic_check=check,
                    progress=progress, cancelled=lambda: job['cancel'])
                job['attempts'] += result.attempts
                job['rejected'].update(result.rejected)
                for sample, params in zip(result.samples, result.params):
                    job['samples'].append({'points': sample, 'params': params, 'status': 'pending',
                                           'source': source['id']})
                job['done'] = len(job['samples'])
                if result.cancelled:
                    job['state'] = 'cancelled'
                    return
            job['state'] = 'done'
            if len(job['samples']) < job['count']:
                job['note'] = (f'Solo {len(job["samples"])} de {job["count"]} variaciones pasaron la validación. '
                               'Prueba un nivel más conservador o un original con mejor detección.')
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            job.update(state='error', error=str(exc))

    def cancel(self, job_id):
        job = self.jobs.get(job_id)
        if job:
            job['cancel'] = True
        return {'cancelled': bool(job)}

    def review(self, job_id, index, action):
        job = self._job(job_id)
        if job['state'] == 'running':
            raise ValueError('Espera a que termine la generación.')
        if not isinstance(index, int) or not 0 <= index < len(job['samples']):
            raise ValueError('Muestra no encontrada.')
        item = job['samples'][index]
        if action in ('approve', 'reject', 'pending'):
            item['status'] = {'approve': 'approved', 'reject': 'rejected', 'pending': 'pending'}[action]
        elif action == 'regenerate':
            source = self.sources.get(item['source'])
            if not source:
                raise ValueError('El archivo original ya no está disponible.')
            result = generator.generate(source['sequence'], 1, job['level'],
                                        seed=int(time.time() * 1000) % (2**31), static=source['static'],
                                        label_text=job['label'])
            if not result.samples:
                raise ValueError('No se obtuvo una variación válida; prueba de nuevo.')
            item.update(points=result.samples[0], params=result.params[0], status='pending')
        else:
            raise ValueError('Acción no válida.')
        return self.public_job(job, start=index, limit=1)

    def save(self, job_id, include_pending=True, save_real=True, participant=''):
        """Guarda las aprobadas (y pendientes, si se indica) en el almacén sintético."""
        from web_dataset import save_sequence
        job = self._job(job_id)
        if job['state'] == 'running':
            raise ValueError('Espera a que termine la generación.')
        label = register_label(job['language'], job['label'])
        statuses = ('approved', 'pending') if include_pending else ('approved',)
        chosen = [s for s in job['samples'] if s['status'] in statuses]
        if not chosen:
            raise ValueError('No hay muestras aprobadas para guardar.')
        real_saved = 0
        participant = str(participant or '').strip()[:60]
        for source_id in job['sources']:
            source = self.sources.get(source_id)
            # Solo un VIDEO aporta una toma real; una foto repetida 30 veces no lo es.
            if save_real and source and source['kind'] == 'video' and not source.get('saved_real'):
                save_sequence(job['language'], label['id'], source['sequence'], metadata={
                    'origin': 'video-import', 'file': source['name'], 'participant': participant,
                    'session_id': f'import-{source_id[:12]}', 'camera': 'archivo'})
                source['saved_real'] = True
                real_saved += 1
        for item in chosen:
            source = self.sources.get(item['source'], {})
            params = item['params']
            save_synthetic(job['language'], label['id'], item['points'], {
                'origin': source.get('kind', 'desconocido'), 'file': source.get('name'),
                'source_digest': source.get('digest'), 'source_id': item['source'],
                'level': job['level'], 'seed': params.seed, 'transform': params.summary(),
                'label_text': label['text'], 'participant': participant,
                'review': item['status'], 'created_at': time.time()},
                sample_id=generator.sample_id(source.get('digest'), params, job['level']))
        job['state'] = 'saved'
        return {'saved': len(chosen), 'real_saved': real_saved, 'label': label}

    def _job(self, job_id):
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError('La generación ya no existe. Vuelve a generar.')
        return job

    @staticmethod
    def public_job(job, start=0, limit=PREVIEW_LIMIT):
        samples = job['samples']
        stats = Counter(s['status'] for s in samples)
        return {'id': job['id'], 'state': job['state'], 'label': job['label'], 'level': job['level'],
                'seed': job['seed'], 'count': job['count'], 'done': job['done'], 'attempts': job['attempts'],
                'rejected': dict(job['rejected']), 'error': job['error'], 'note': job.get('note'),
                'semantic': job.get('semantic'), 'elapsed': round(time.time() - job['started'], 1),
                'review': {'approved': stats['approved'], 'rejected': stats['rejected'], 'pending': stats['pending']},
                'previews': [{'index': i, 'status': samples[i]['status'], 'params': samples[i]['params'].summary(),
                              'frames': _compact_frames(samples[i]['points'])}
                             for i in range(start, min(len(samples), start + limit))] if job['state'] != 'running' else []}

    def state(self, language, job_id=None, start=0):
        sources = [self.public_source(s) for s in self.sources.values() if s['language'] == language]
        job = self.jobs.get(job_id) if job_id else next(iter(self.jobs.values()), None)
        return {'sources': sources, 'job': self.public_job(job, start) if job and job['language'] == language else None,
                'counts': list(COUNTS), 'levels': list(generator.LEVELS)}


STUDIO = SyntheticStudio()
