# Índice de funciones y métodos de Seña

Este catálogo complementa los comentarios junto al código: permite ubicar cada función sin recorrer todo el repositorio. Las descripciones se refieren al comportamiento implementado; los módulos heredados o experimentales están marcados como tales.

## Python

### `accounts.py`

- `digest(value)` — Calcula el hash SHA-256 de un token para no almacenarlo en claro en SQLite.
- `class Accounts` — Gestiona las cuentas del modo de equipo heredado; el modo local actual no exige iniciar sesión.
- `__init__(self, path)` — Conserva la ruta de la base SQLite sin abrir una conexión permanente.
- `db(self)` — Abre una transacción, crea las tablas si faltan y cierra la conexión al terminar.
- `configured(self)` — Indica si ya se registró alguna cuenta en este servidor.
- `public(row)` — Devuelve únicamente los campos de usuario que pueden enviarse al navegador.
- `session(self, token)` — Valida caducidad y actividad de la sesión y devuelve usuario y token CSRF.
- `issue(self, user_id=None, previous=None)` — Emite tokens aleatorios de sesión y CSRF; sustituye la sesión anterior si corresponde.
- `logout(self, token)` — Elimina la sesión identificada por el hash del token recibido.
- `validate(username, name, password)` — Comprueba formato y longitud de usuario, nombre y contraseña antes del registro.
- `register(self, username, name, password, invite=None, bootstrap=False)` — Registra una cuenta con contraseña derivada y consume una invitación de un solo uso.
- `throttle(self, identity, limit=10)` — Cuenta intentos por identidad y bloquea temporalmente el acceso cuando supera el límite.
- `clear_throttle(self, identity)` — Borra el contador de intentos de una identidad después de autenticarla.
- `login(self, username, password)` — Verifica usuario y contraseña con PBKDF2 y comparación de tiempo constante.
- `invite(self, admin_id)` — Crea una invitación aleatoria con caducidad para añadir un colaborador.
- `users(self)` — Lista los datos públicos de las cuentas en orden de creación.
- `enable(self, identifier)` — Reactiva una cuenta colaboradora sin modificar administradores.
- `disable(self, identifier, actor)` — Desactiva un colaborador y revoca sus sesiones; impide desactivar al propio actor.

### `admin_auth.py`

- `class AdminGuard` — Protege las operaciones administrativas con contraseña derivada y límite de intentos.
- `__init__(self, config_path)` — Inicializa la ruta de credenciales y los contadores de bloqueo temporal.
- `verify(self, password)` — Comprueba la contraseña contra PBKDF2; rechaza credenciales inválidas o intentos bloqueados.

### `alphabets.py`

- `alphabet_for(language)` — Obtiene los símbolos y notas del abecedario correspondiente al perfil validado.
- `find_symbol_label(labels, symbol)` — Busca si un símbolo ya tiene una etiqueta equivalente para evitar duplicarlo.
- `alphabet_status(language, rows, model)` — Combina símbolos, ejemplos y vocabulario aprendido para mostrar el progreso del abecedario.
- `entries(symbols)` — Construye las filas de símbolos con su etiqueta, cantidad de ejemplos y estado entrenado.
- `add_alphabet(language, extras=False)` — Registra los símbolos de un perfil sin inventar ejemplos ni modificar sus modelos.
- `add_all_alphabets()` — Registra los símbolos del perfil español sin crear ejemplos de entrenamiento.

### `capture_quality.py`

- `landmark_quality(points)` — Comprueba manos completas, tamaño de palma, límites del encuadre y visibilidad del torso.
- `image_quality(image)` — Mide brillo y variación del Laplaciano para advertir oscuridad, exceso de luz o poco enfoque.
- `sequence_quality(points)` — Resume la proporción de detecciones utilizables y advierte movimiento al final de una toma.
- `hand_image_quality(image, points)` — Evalúa luz y enfoque dentro de las regiones de manos, usando las mismas coordenadas que el detector.

### `data_collection.py`

- `create_folder_structure()` — Crea todos los directorios necesarios para el dataset y el proyecto.
- `_draw_waiting_screen(image: np.ndarray, action: str, seq_idx: int, total_seqs: int, logo_lia, logo_cec, global_progress: float)` — Pantalla de espera entre secuencias. El usuario debe presionar SPACE.
- `_draw_recording_ui(image: np.ndarray, action: str, seq_idx: int, frame_num: int, total_seqs: int, logo_lia, logo_cec)` — UI durante la grabación activa de una secuencia.
- `collect_data()` — Pipeline completo de recolección de datos.

### `dataset_tools.py`

- `digest(points)` — Calcula la huella de una secuencia de puntos para identificar copias exactas.
- `sample_rows(language)` — Inspecciona los archivos de un perfil y describe validez, calidad, duplicados y procedencia.
- `audit_dataset(language)` — Resume problemas del dataset para mostrarlos en la revisión de grabaciones.
- `export_dataset(language)` — Construye un ZIP con manifiesto y ejemplos válidos de una sola lengua.
- `import_dataset(language, encoded)` — Valida el ZIP completo, sus rutas y muestras antes de incorporar ejemplos compatibles.
- `training_provenance(language, raw, targets, labels)` — Agrupa ejemplos por personas o sesiones y vincula copias para impedir fugas entre conjuntos.
- `root(value)` — Encuentra el representante de un grupo y comprime sus enlaces de equivalencia.
- `group_for(row)` — Deriva la identidad de agrupación a partir de participante, sesión o huella histórica.
- `grouped_split(targets, groups, seed=42)` — Busca un reparto por grupos completos donde todas las clases estén representadas en cada conjunto.
- `inspect_sample(language, identifier)` — Devuelve metadatos y curvas escalares de movimiento y calidad para revisar una toma.
- `persistent_split(targets, groups, path, seed=42, fingerprints=None)` — Conserva el destino histórico de grupos y huellas al ampliar el vocabulario.

### `discriminative_learning.py`

- `class HardExampleSequence` — Entrega lotes de entrenamiento con pesos equilibrados según la dificultad de cada ejemplo.
- `__init__(self, points, targets, batch_size=16, seed=42)` — Conserva muestras y objetivos e inicializa pesos y orden aleatorio reproducible.
- `__len__(self)` — Calcula cuántos lotes hacen falta para recorrer los ejemplos.
- `__getitem__(self, index)` — Devuelve las entradas, etiquetas y pesos del lote solicitado por Keras.
- `on_epoch_end(self)` — Reordena las muestras al terminar una época sin cambiar su clase.
- `class MineHardExamples` — Actualiza periódicamente los pesos de los ejemplos difíciles usando solo entrenamiento.
- `__init__(self, sequence)` — Vincula el callback con la secuencia que recibirá los pesos nuevos.
- `on_epoch_end(self, epoch, logs=None)` — Evalúa la dificultad por lotes y ajusta los pesos después de las épocas iniciales.
- `supervised_contrastive_loss(labels, embeddings, temperature=0.15)` — Acerca representaciones de la misma clase y separa las distintas en un lote supervisado.
- `contrastive_warmup(encoder, points, targets, epochs=4, seed=42)` — Preentrena el codificador con pares de la misma clase tomados exclusivamente del entrenamiento.
- `step(x, y)` — Calcula la pérdida contrastiva y aplica gradientes sobre los pesos del codificador.

### `main.py`

- `class LSMRecognizer` — Sistema completo de reconocimiento de LSM dinámica en tiempo real.
- `__init__(self)` — Inicializa el reconocedor de escritorio, cámara, buffers, historial y recursos gráficos.
- `_load_model(self)` — Carga el modelo LSTM y el mapa de etiquetas desde disco.
- `_run_inference(self)` — Ejecuta una pasada del modelo LSTM sobre el buffer actual.
- `_reset_state(self)` — Vacía el buffer y resetea todo el estado de predicción.
- `_update_fps(self)` — Calcula FPS suavizado usando una ventana deslizante de 30 frames.
- `_render_ui(self, image: np.ndarray, fps: float)` — Dibuja todos los elementos gráficos sobre el frame actual.
- `_save_session(self)` — Guarda la oración acumulada en un archivo .txt con timestamp.
- `run(self)` — Bucle principal de captura, procesamiento y visualización.
- `main()` — Punto de entrada: configura GPU y lanza el reconocedor.

### `model.py`

- `build_web_model(num_classes: int, learning_rate: float=0.0005, input_dim: int=FEATURE_DIM)` — BiLSTM más compacto para datasets personales con pocas decenas de ejemplos.
- `build_lstm_model(num_classes: int=len(ACTIONS), learning_rate: float=0.001)` — LSTM Bidireccional con capa de proyección temporal.
- `build_attention_model(num_classes: int=len(ACTIONS), learning_rate: float=0.0005)` — BiLSTM con Mecanismo de Atención Multi-Cabeza.

### `motion_features.py`

- `tracks(points)` — Extrae trayectorias de muñecas y puntas de dedos en coordenadas relativas al cuerpo.
- `trajectory_descriptor(points)` — Resume desplazamiento, velocidad con signo y recorrido conservando orden y lateralidad.
- `motion_summary(points)` — Mide amplitud y velocidad final para describir cuánto movimiento contiene una secuencia.
- `fit_motion_profile(points, targets)` — Estima qué clases necesitan movimiento a partir de sus ejemplos de entrenamiento.
- `augment_timing(points, targets)` — Genera variantes de velocidad y breve postura final sin invertir el recorrido.
- `motion_challenges(points, targets, profile, guard, labels)` — Comprueba el filtro temporal con variantes congeladas, invertidas o recortadas; no mide precisión global.

### `private_server.py`

- `class SetupError` — Representa un fallo controlado de la configuración privada heredada.
- `cli_path()` — Localiza el ejecutable instalado de Tailscale sin instalarlo ni iniciar sesión.
- `command(args, timeout=15)` — Ejecuta un comando con tiempo límite y transforma sus fallos en mensajes de configuración.
- `read_json_output(args)` — Ejecuta una consulta y exige que devuelva un objeto JSON válido.
- `discover_origin(status)` — Deriva el origen HTTPS del nombre DNS de una Mac conectada a Tailscale.
- `check_proxy(config, origin)` — Comprueba que Serve pertenezca a Seña y que no haya Funnel u otro servicio que se sobrescribiría.
- `configured_admin()` — Consulta si existe una cuenta administradora activa para el despliegue autenticado heredado.
- `training_active()` — Comprueba si el último trabajo de entrenamiento sigue vivo antes de cambiar el servicio.
- `current_config()` — Lee y valida la configuración privada persistida en disco.
- `write_config(origin)` — Guarda el origen privado de forma atómica y con permisos restringidos.
- `configure(enable)` — Activa o desactiva el despliegue autenticado heredado preservando configuraciones ajenas.
- `wait_for_backend(origin, attempts=30)` — Espera a que el backend acepte el Host HTTPS configurado antes de publicar el proxy.
- `agent_definition()` — Construye la definición del servicio LaunchAgent de macOS.
- `install_agent()` — Instala y arranca el supervisor local después de comprobar sus condiciones de funcionamiento.
- `run_backend()` — Supervisa una única instancia hija y la reinicia al cambiar el origen del modo autenticado.
- `stop(*_)` — Marca la solicitud de parada para cerrar ordenadamente el proceso hijo.
- `verify_private_https(origin)` — Verifica TLS y que el despliegue heredado exija autenticación para acceder al estado.
- `status()` — Muestra el diagnóstico del despliegue autenticado heredado y la conexión de Tailscale.
- `main()` — Selecciona la acción de administración del servicio privado recibida por línea de comandos.

### `recognition_analysis.py`

- `temperature_probabilities(probabilities, temperature=1.0)` — Aplica calibración por temperatura sin cambiar el orden de las clases predichas.
- `fit_temperature(probabilities, targets)` — Busca una temperatura con la pérdida de validación, sin ajustar con la prueba reservada.
- `accepted_mask(probabilities, policy, allowed=None, strict=False)` — Combina confianza, margen y permisos por clase para decidir qué predicciones se aceptan.
- `calibrate_policy(probabilities, targets, allowed)` — Ajusta umbrales por clase con evidencia de validación y deja sin soporte las clases insuficientes.
- `confusion_analysis(matrix, labels)` — Identifica pares y grupos de clases que se confunden a partir de la matriz de confusión.
- `evaluate(probabilities, targets, labels, policy=None, allowed=None)` — Calcula métricas globales, por clase y de rechazos sobre las probabilidades proporcionadas.
- `hard_weights(probabilities, targets)` — Asigna más peso a ejemplos difíciles conservando un peso total equilibrado por clase.
- `regression_check(candidate, previous, tolerance=0.05)` — Detecta deterioros por clase al comparar dos modelos en los mismos ejemplos independientes.
- `dataset_summary(raw, y, labels, groups, provenance)` — Resume soporte, grupos y desbalance de las clases seleccionadas para el entrenamiento.
- `deduplicate(raw, y)` — Elimina secuencias idénticas y rechaza copias con etiquetas contradictorias.
- `preprocessing_probe(raw, targets, train, validation)` — Compara diagnósticos de características para detectar posibles problemas de representación.
- `label_review_candidates(raw, targets, labels, train)` — Prioriza ejemplos cuya predicción discrepa de su etiqueta para revisarlos, sin renombrarlos automáticamente.

### `recognition_decision.py`

- `evidence(points, predicted, metadata)` — Mide distancia de forma, rival y trayectoria de una predicción respecto a sus referencias aprendidas.
- `batch_evidence(points, probabilities, metadata)` — Calcula las evidencias geométricas de todas las secuencias evaluadas.
- `gate_masks(probabilities, policy, scores, strict=False)` — Construye máscaras separadas de forma, rival, trayectoria y confianza según la política guardada.
- `policy_allowed(probabilities, policy, scores)` — Combina los filtros geométricos para usarlos también durante la evaluación fuera de cámara.
- `calibrate_joint_policy(probabilities, targets, scores, hand_guard=None, groups=None, motion_guard=None)` — Ajusta conjuntamente los filtros por clase para maximizar cobertura con precisión empírica suficiente.
- `rejection_report(probabilities, targets, labels, policy, scores)` — Describe en qué etapa se rechazan secuencias y qué clases carecen de soporte fiable.
- `decision_details(points, probabilities, metadata, strict=False, test_mode=False)` — Aplica la política versionada y devuelve aceptación o una razón concreta de rechazo.

### `recognition_features.py`

- `feature_dimension(preprocessing)` — Devuelve el número de canales esperado por cada versión y rechaza versiones desconocidas.
- `local_hands(points)` — Expresa la forma de cada mano respecto a muñeca y palma sin intercambiar lados ni eliminar orientación.
- `prepare_sequence(points, preprocessing=HAND_PREPROCESSING)` — Aplica exactamente el preprocesamiento indicado por los metadatos del modelo.
- `hand_descriptor(points, contrastive=False, descriptor_version=None)` — Resume la forma de manos y, según la versión, la flexión y orientación de sus articulaciones.
- `nearest_distance(descriptor, references)` — Promedia las distancias a las referencias más próximas para reducir el efecto de una sola muestra.
- `fit_hand_guard(train_points, train_targets, val_points, val_targets, contrastive=False, descriptor_version=None)` — Aprende referencias con entrenamiento y calibra el rechazo de forma con validación.
- `hand_guard_accept(points, predicted, guard)` — Comprueba distancia absoluta y separación de formas rivales con el descriptor guardado.
- `regions(points)` — Presenta los canales planos como vistas de pose, rostro, mano izquierda y mano derecha.
- `normalize_sequence(points)` — Centra y escala con hombros visibles conservando movimiento y puntos ausentes.
- `augment_viewpoints(points, targets, seed=42)` — Simula pequeñas variaciones constantes de cámara por secuencia, sin reflejar manos.
- `augment_training(points, targets, seed=42)` — Crea las variantes de ruido y escala del entrenamiento de referencia histórico.
- `decision_metrics(probabilities, targets, threshold=0.85, margin=0.15, allowed=None)` — Calcula aceptación, cobertura y aciertos bajo un umbral y margen determinados.
- `validation_threshold(probabilities, targets)` — Elige un umbral con validación cuando existe soporte suficiente de predicciones aceptadas.
- `smooth_landmarks(points)` — Filtra de forma causal los puntos visibles sin rellenar manos ausentes ni mezclar tomas.
- `normalize_face(body)` — Normaliza el rostro con referencias oculares suficientes para preservar su expresión local.
- `temporal_descriptor(points, preprocessing=STABLE_PREPROCESSING, descriptor_version=None)` — Extrae el resumen temporal correspondiente a la versión guardada en el filtro.
- `fit_temporal_guard(points, targets, validation, val_targets, descriptor_version=None)` — Aprende referencias de trayectorias y ajusta límites con secuencias de validación.
- `temporal_guard_score(points, predicted, guard)` — Compara la trayectoria con su clase y, si corresponde, con rivales de distinto movimiento.
- `temporal_guard_accept(points, predicted, guard)` — Acepta la trayectoria solamente cuando su puntuación permanece dentro del límite calibrado.
- `calibrate_decision(probabilities, targets, allowed=None)` — Busca confianza y margen en validación respetando los filtros geométricos disponibles.
- `finger_geometry(points)` — Mide extensión de dedos y separación de puntas en unidades de palma.
- `articulation_motion(points)` — Extrae ángulos, orientación, velocidades y relaciones entre manos preservando su lateralidad.
- `unit(v)` — Normaliza vectores evitando divisiones por cero en puntos degenerados.
- `velocity(v, present)` — Calcula diferencias temporales solo entre observaciones consecutivas donde la mano está presente.
- `augment_articulation(points, targets, seed=42)` — Añade perturbaciones pequeñas y correlacionadas en unidades de palma para simular ruido de seguimiento.
- `representative_references(references, limit=64)` — Selecciona un conjunto acotado y reproducible de referencias representativas para limitar el coste en vivo.
- `augment_robust(points, targets, seed=42)` — Combina distancia, velocidad y ruido de seguimiento sobre puntos crudos sin aumentar el volumen habitual de variantes.

### `rig_overlay.py`

- `rig_payload(points, width, height)` — Construye el formato auxiliar heredado del rig; el protocolo web activo usa hand_rig.
- `visible_points(region, visibility=False)` — Convierte puntos finitos y visibles en coordenadas para el formato auxiliar.

### `sign_languages.py`

- `language_info(language)` — Valida el identificador y devuelve los datos del perfil de lengua de señas.
- `labels_for(language)` — Combina las etiquetas predeterminadas en español con el vocabulario personalizado de LSM.
- `validate_label(language, label)` — Rechaza etiquetas que no pertenecen al vocabulario de la lengua seleccionada.
- `dataset_dir(language)` — Devuelve la carpeta de ejemplos de un perfil validado.
- `model_dir(language)` — Devuelve la carpeta de versiones de modelos de un perfil validado.
- `pipeline_spec()` — Describe el contrato de captura necesario para comprobar compatibilidad de datos y modelos.
- `clean_sign_name(name)` — Normaliza espacios y Unicode y rechaza nombres vacíos, excesivos o con caracteres de control.
- `custom_labels(language)` — Carga y comprueba las etiquetas personalizadas persistidas para una lengua.
- `register_label(language, name)` — Reutiliza una etiqueta equivalente o registra una nueva de forma atómica dentro del perfil.

### `snapshot_recognition.py`

- `descriptor(frame, guard)` — Extrae únicamente la parte estática del descriptor de mano para comparar una imagen.
- `distances(frame, bundle)` — Calcula la distancia de la postura capturada a las referencias entrenadas de cada clase.
- `build_snapshot(metadata, validation, targets)` — Calibra límites del experimento con la reserva de validación y excluye clases de movimiento.
- `classify_snapshot(frame, bundle)` — Devuelve una forma confirmada o rechazo por movimiento, soporte insuficiente, distancia o ambigüedad.

### `studio_services.py`

- `versions(language)` — Lista versiones compatibles y sus diagnósticos sin enviar todas las referencias geométricas al navegador.
- `activate_version(language, version)` — Valida vocabulario, archivos y dimensiones antes de cambiar atómicamente la versión activa.
- `recent_activity()` — Resume trabajos y operaciones recientes usando una caché basada en archivos modificados.
- `dataset_operation(runtime, route, payload)` — Enruta auditoría, importación, exportación y cambios administrativos dentro de una sola lengua.

### `team_access.py`

- `cookie_token(handler)` — Lee de forma segura el token opaco de la cookie de sesión.
- `set_session(handler, token)` — Configura la cookie HttpOnly y SameSite con marca Secure en el despliegue HTTPS autenticado.
- `local_session(handler)` — Proporciona una identidad local cuando las cuentas están desactivadas y la conexión es de loopback.
- `status(handler, accounts)` — Devuelve el estado de acceso local o una sesión de cuenta para la pantalla de entrada.
- `close_user_cameras(runtime, identifier)` — Cierra los detectores y elimina todas las sesiones de cámara de un usuario.
- `authenticate(handler, accounts, require_user=True)` — Resuelve la identidad local o valida la sesión de cuenta requerida por la ruta.
- `csrf_valid(handler, session)` — Compara el token de mutación con el CSRF de la sesión mediante comparación constante.
- `auth_post(handler, route, payload, accounts, runtime, session)` — Procesa registro, acceso e invitaciones del modo autenticado; los rechaza en modo local.
- `status_after_login(accounts, token)` — Devuelve la identidad y el CSRF nuevos después de cambiar de sesión.
- `draft_owner(language, identifier)` — Consulta la procedencia de una toma pendiente o su recibo para verificar su propietario.
- `authorize(runtime, user, route, payload)` — Comprueba roles, consentimiento y propiedad de cámara o toma antes de una operación.
- `shared_state(runtime, user, csrf)` — Añade identidad y CSRF al estado y filtra tomas ajenas cuando el usuario no es administrador.

### `train.py`

- `load_dataset()` — Recorre LSM_Dataset/ y carga todas las secuencias como arrays NumPy.
- `plot_training_history(history: tf.keras.callbacks.History, save_dir: str=MODELS_DIR)` — Gráfica de accuracy y loss para train/validación.
- `plot_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, label_map: dict[int, str], save_dir: str=MODELS_DIR)` — Matriz de confusión normalizada para el conjunto de test.
- `class EpochLogger` — Imprime un resumen compacto al final de cada época.
- `on_epoch_end(self, epoch: int, logs: dict | None=None)` — Escribe el progreso de cada época del entrenamiento de escritorio en el registro.
- `train()` — Pipeline completo: cargar datos → entrenar → evaluar → guardar.

### `utils.py`

- `mediapipe_detection(image: np.ndarray, model)` — Procesa un frame BGR con MediaPipe Holistic con mínima copia de memoria.
- `draw_styled_landmarks(image: np.ndarray, results)` — Dibuja todos los landmarks con estilos de color diferenciados por región.
- `_landmarks_to_array(landmark_list, zero_size: int, indices: list[int] | None=None, n_coords: int=3)` — Convierte una NormalizedLandmarkList a un vector NumPy float32.
- `extract_keypoints(results)` — Extrae y concatena todos los landmarks en un único vector 1-D por frame.
- `hands_detected(results)` — Devuelve True si al menos una mano es visible en el frame actual.
- `load_logo(path: str, target_height: int)` — Carga un logo PNG (con o sin canal alfa) y lo redimensiona
- `overlay_png(background: np.ndarray, overlay: np.ndarray, x: int, y: int)` — Superpone una imagen BGRA sobre un fondo BGR usando el canal alfa.
- `draw_prediction_box(image: np.ndarray, text: str, confidence: float, color: tuple[int, int, int]=(0, 230, 0))` — Panel inferior semitransparente con:
- `draw_buffer_indicator(image: np.ndarray, current_len: int, max_len: int)` — Barra horizontal delgada que muestra el llenado del buffer de secuencia.
- `draw_stability_bar(image: np.ndarray, stable_count: int, stability_frames: int)` — Indicador de estabilidad: muestra cuántos frames consecutivos lleva
- `draw_sentence_builder(image: np.ndarray, words: list[str])` — Muestra las palabras confirmadas en la parte superior central del frame,

### `validation_protocol.py`

- `calibration_split(targets, groups, validation, path, fingerprints=None)` — Separa selección y calibración dentro de validación; declara explícitamente cuando deben compartir datos.
- `describe(part)` — Cuenta ejemplos y grupos por clase para describir la independencia de la reserva.
- `fallback(reason)` — Devuelve validación compartida con su motivo cuando no hay datos para dos reservas distintas.
- `root(group)` — Agrupa copias de una secuencia para impedir que entren en roles distintos.
- `wilson_interval(successes, total, z=1.959963984540054)` — Calcula un intervalo orientativo de incertidumbre para un conteo de éxitos sobre observaciones.
- `validation_support(targets, groups, labels, predicted=None, accepted=None)` — Describe soporte e incertidumbre por muestras y grupos sin afirmar independencia entre personas.
- `row(truth, chosen)` — Calcula soporte, cobertura e intervalos de una clase o del total evaluado.

### `web_app.py`

- `model_metadata(language)` — Valida el manifiesto activo, la lengua, el pipeline y los archivos del modelo antes de cargarlo.
- `class Session` — Conserva detectores, buffers, procedencia y estado de una cámara; no representa una cuenta de usuario.
- `__init__(self, language)` — Inicializa una cámara con sus detectores diferidos y contadores de seguimiento.
- `reset(self)` — Vacía la secuencia y sus votos de reconocimiento sin cerrar la cámara ni borrar tomas guardadas.
- `close(self)` — Libera los detectores de video e imagen independientes de esta sesión.
- `class Runtime` — Coordina cámaras, modelos, salas temporales, administración y entrenamiento del servidor.
- `__init__(self)` — Crea el bloqueo compartido, las cachés y los registros en memoria del servidor.
- `create_conversation(self, language, phone_origin)` — Abre una sala temporal con llaves separadas y genera su QR local cuando existe origen móvil HTTPS.
- `conversation(self, identifier, key, side)` — Valida la llave del participante y elimina salas vencidas antes de permitir su uso.
- `conversation_message(self, room, sender, text, kind='text', confidence=None)` — Normaliza y añade un mensaje al historial acotado en memoria de la sala.
- `flush_sign_drafts(self, room)` — Publica cada borrador que lleva cuatro segundos sin una seña confirmada nueva.
- `append_conversation_sign(self, room, side, text, confidence)` — Acumula letras o palabras por participante y reinicia la pausa de envío automático.
- `conversation_state(self, room)` — Publica borradores vencidos y devuelve mensajes, conexión y tiempo restante de una sala.
- `close_conversation(self, identifier)` — Revoca la sala y libera la cámara del teléfono asociada.
- `phone_request(self, route, payload)` — Atiende mensajes, cámara y fotos del teléfono limitados a la sala autorizada por su llave.
- `invalidate_label_model(self, language, label)` — Desactiva un modelo que contiene una clase modificada para evitar reconocer datos retirados.
- `delete_recordings(self, payload)` — Verifica administración y confirmación antes de archivar los ejemplos de una etiqueta.
- `new_session(self, language, participant='', camera='', quality_gate=False)` — Recupera sesiones inactivas y abre una cámara con perfil y procedencia independientes.
- `session(self, identifier)` — Valida una sesión de cámara y renueva su marca de actividad.
- `start_capture(self, identifier, consecutive=False, batch_id='')` — Comprueba límites y operaciones pendientes y prepara una secuencia nueva para grabar.
- `job(self)` — Lee el progreso del entrenamiento y detecta trabajos cuyo proceso se interrumpió.
- `training(self)` — Comprueba si sigue vivo un entrenamiento iniciado o recuperado después de reiniciar.
- `state(self)` — Reúne perfiles, vocabularios, ejemplos, modelos, actividad y trabajo para la interfaz.
- `prepare_snapshot(self, language)` — Prepara el comparador de fotos con referencias entrenadas y grabaciones únicas de validación congelada.
- `image_detector(self, item)` — Crea bajo demanda el detector independiente usado por fotos y recuperación del seguimiento.
- `recover_hand_tracking(self, item, mirrored, result, now)` — Reintenta una pérdida reciente sobre la misma imagen, con frecuencia acotada y sin inventar puntos.
- `analyze_snapshot(self, identifier, encoded)` — Valida una imagen, detecta su postura de forma independiente y ejecuta la comparación experimental.
- `model_signature(self, language, directory)` — Obtiene firmas de manifiesto, metadatos y pesos para invalidar la caché cuando cambian.
- `load_model(self, language)` — Reutiliza un modelo sin cambios o valida y carga pesos y filtros compatibles desde disco.
- `frame(self, payload)` — Procesa un fotograma: seguimiento, calidad, captura o inferencia con filtros y confirmación temporal.
- `start_training(self, language, epochs, label_ids=None, strategy='baseline')` — Valida clases, épocas y estado y lanza el entrenamiento en un proceso separado.
- `class Handler` — Implementa las rutas HTTP, la entrega de recursos y los controles de origen y autorización.
- `setup(self)` — Configura la conexión y el tiempo de espera antes de recibir peticiones HTTP.
- `log_message(self, format, *args)` — Registra solicitudes evitando ruido por fotogramas y exposición de llaves de salas en rutas.
- `send_data(self, status, data, content_type='application/json; charset=utf-8')` — Envía JSON o bytes con longitud, cabeceras de seguridad y cierre ante errores HTTP.
- `trusted_host(self)` — Permite únicamente los Hosts configurados para la aplicación principal.
- `trusted_phone_host(self, origin=False)` — Comprueba Host y, en mutaciones, Origin exactos del acceso móvil HTTPS.
- `do_GET(self)` — Entrega la aplicación, la página móvil autorizada, recursos permitidos y estado autenticado.
- `do_POST(self)` — Valida tamaño, JSON, origen, token y permisos antes de ejecutar cada operación de la API.
- `main()` — Valida los argumentos de arranque, configura el servidor y libera detectores al cerrarlo.

### `web_dataset.py`

- `validate_sequence(points)` — Exige una secuencia finita de dimensiones compatibles y detecciones suficientes.
- `save_sequence(language, label, points, sample_id=None, metadata=None)` — Guarda puntos, contrato de captura y procedencia en un NPZ mediante reemplazo atómico.
- `load_sequence(path)` — Lee un NPZ sin pickle y verifica su contrato y dimensiones antes de usarlo.
- `inventory(language)` — Cuenta ejemplos válidos e inválidos por etiqueta y reutiliza el resultado si los archivos no cambiaron.
- `archive_label(language, label)` — Traslada todos los ejemplos de una etiqueta a una carpeta recuperable con registro de la operación.
- `read_dataset(language, minimum, label_ids=None)` — Carga únicamente las clases seleccionadas y exige suficientes ejemplos antes de entrenar.
- `split_per_class(y, seed=42)` — Proporciona la separación histórica por clase usada por compatibilidad y pruebas; no sustituye el reparto agrupado web.
- `validate_identifier(identifier)` — Restringe los identificadores de muestras y versiones a 32 caracteres hexadecimales.
- `draft_dir(language)` — Deriva la carpeta de tomas pendientes a partir de una lengua previamente validada.
- `save_draft(language, points, metadata=None)` — Guarda una toma completa aún sin nombre con su procedencia y un identificador único.
- `pending_drafts(language)` — Lista tomas pendientes de la lengua en orden de creación.
- `commit_draft(language, identifier, name)` — Asigna nombre, conserva procedencia e integra una toma de forma idempotente sin duplicarla al reintentar.
- `discard_draft(language, identifier)` — Retira una toma pendiente hacia su subcarpeta recuperable de descartadas.
- `sequence_metadata(path)` — Lee y valida el diccionario de procedencia almacenado en una secuencia.

### `web_train.py`

- `retained_label_ids(language, label_ids)` — Incluye clases anteriores que conservan ejemplos para no entrenar solamente el vocabulario nuevo.
- `validation_summary(probabilities, targets, allowed, threshold, margin=0.15)` — Resume aciertos, F1 y aceptación para comparar resultados de validación.
- `class_decisions(probabilities, targets, allowed, threshold, margin, labels)` — Calcula precisión de aceptaciones, recuperación y cobertura separadas por clase.
- `candidate_is_not_worse(candidate, previous)` — Compara métricas globales del candidato y el anterior cuando existe una referencia comparable.
- `write_json(path, payload)` — Escribe progreso o metadatos en un archivo temporal y lo sustituye atómicamente.
- `train_language(language, epochs, job_id, label_ids=None, strategy='baseline', activate=True)` — Ejecuta separación, aumentos, entrenamiento, calibración, evaluación y posible activación de una versión.
- `class BalancedValidation` — Calcula una métrica de selección que considera F1 macro y la clase con menor recuperación.
- `on_epoch_end(self, epoch, logs=None)` — Evalúa la reserva de selección y añade las métricas equilibradas a los registros de la época.
- `class Progress` — Publica en disco el avance que la interfaz consulta durante el entrenamiento.
- `on_epoch_end(self, epoch, logs=None)` — Añade métricas e historia de la época y actualiza el trabajo de entrenamiento.
- `compare_previous(indices_set, candidate_probs, candidate_allowed, final_test=False)` — Compara modelos solo en ejemplos comunes ajenos a sus entrenamientos y calibraciones.

## JavaScript

### `static/app.js`

- `function notice(message, error = false)` — Muestra o limpia una notificación general, indicando si es un error.
- `async function api(path, body)` — Envía JSON a la API con el CSRF actual y convierte errores HTTP en mensajes utilizables.
- `function makeOption(value, text)` — Crea una opción de selector usando texto seguro, sin interpretar HTML.
- `function render()` — Actualiza vocabulario, controles y estados habilitados según cámara, perfil y operaciones en curso.
- `function renderAlphabet()` — Dibuja los símbolos y su progreso y permite elegir una letra para nombrar la siguiente toma.
- `async function addAlphabet(scope, extras = false)` — Solicita registrar símbolos del perfil LSM, sin crear ejemplos ficticios.
- `function renderJob()` — Muestra estado, época y métricas del trabajo real de entrenamiento.
- `async function refresh()` — Reutiliza la consulta de estado en curso y solo vuelve a dibujar cuando cambian sus datos.
- `async function selectLanguage(id)` — Detiene la cámara, cambia el perfil y limpia estados que no deben cruzarse entre lenguas.
- `async function selectMode(next)` — Traduce los modos históricos a las vistas actuales del estudio.
- `function resetResult()` — Restaura el panel de reconocimiento sin inventar candidatos o confianza.
- `function renderAdmin()` — Actualiza opciones de borrado y sus requisitos según vocabulario, operación y permisos.
- `async function deleteRecordings(event)` — Envía el borrado administrativo confirmado y actualiza el estado después de archivar ejemplos.
- `async function refreshCameras()` — Enumera cámaras disponibles y conserva la selección si el dispositivo sigue conectado.
- `async function startCamera()` — Solicita permiso, abre la cámara seleccionada y crea su sesión de procesamiento en el servidor.
- `async function stopCamera()` — Cancela cuentas atrás y tandas, apaga pistas y libera la sesión de cámara remota.
- `async function sendFrame(mark)` — Captura un fotograma conservando proporción y calidad, lo procesa y programa el siguiente sin solapar envíos.
- `function showPrediction(result)` — Presenta aceptación o rechazo y añade solamente confirmaciones estables al historial y la voz.
- `function renderHistory()` — Dibuja las confirmaciones y actualiza aciertos comprobados y exportación de sesión.
- `function clearHistory()` — Limpia historial, estadísticas locales y resultado visible de reconocimiento.
- `async function recordExample(automatic = false, serial = null)` — Espera la preparación elegida y solicita una toma completa, comprobando cancelaciones de tanda.
- `function renderBatchCounter()` — Muestra completas/objetivo en la cámara y mantiene su etiqueta accesible.
- `async function startContinuous()` — Valida tamaño y pausa y comienza la primera captura de una tanda consecutiva.
- `async function toggleContinuousPause()` — Pausa entre tomas o al terminar la actual y reanuda conservando el progreso.
- `async function stopContinuous()` — Cierra la cámara y conserva las tomas completas pendientes de nombrar.
- `async function saveNamedCapture(event)` — Integra una toma pendiente con su significado en el vocabulario del perfil seleccionado.
- `async function discardCapture()` — Retira una toma pendiente sin incorporarla al entrenamiento.
- `async function trainModel()` — Cierra la cámara y solicita entrenar las clases y estrategia elegidas.
- `function speak()` — Añade la última confirmación a la cola de voz con el idioma del perfil.
- `function capturePauseShortcut(event)` — Usa Espacio para pausar o continuar Dataset sin interferir con escritura, diálogos ni otras vistas.
- `function clearHandRig()` — Borra el dibujo y cancela su vencimiento para no dejar puntos antiguos sobre la cámara.
- `function drawHandRig(hands, width, height, sourceFrame = null)` — Dibuja la imagen analizada reflejada una vez y sus puntos sincronizados, no el video adelantado.
- `function setHandRig(enabled, persist = true)` — Activa o desactiva el rig y conserva la preferencia visual en el navegador.
- `async function takeSnapshot()` — Captura una imagen en memoria y muestra comparación experimental o rechazo, sin probabilidad inventada.

### `static/studio.js`

- `function node(tag, text, className)` — Crea un elemento de interfaz con texto seguro y clase opcional.
- `function icon(name)` — Construye un icono SVG desde el recurso Lucide local.
- `function selectedTrainingClasses(p)` — Filtra las etiquetas seleccionadas que tienen el mínimo de ejemplos requerido.
- `async function cameraFingerprint(id)` — Deriva una huella corta del identificador de cámara en vez de guardar el identificador original.
- `function sessionConfirmedText(result)` — Describe la etapa provisional de estabilidad sin tratarla como una confirmación.
- `function renderAlternatives(items)` — Muestra candidatos orientativos separados del resultado confirmado.
- `async function navigateStudio(view)` — Cambia de vista y mueve el único espacio de cámara a Dataset o Reconocimiento.
- `function historyReplace(view)` — Actualiza el fragmento de URL para conservar la vista sin recargar la aplicación.
- `function applyTheme(value)` — Aplica apariencia clara, oscura o del sistema y guarda la preferencia local.
- `function renderStudio()` — Compone estadísticas, perfiles, actividad, métricas y gráficos a partir del estado real.
- `function filterVocabulary()` — Oculta filas que no coinciden con el texto de búsqueda del vocabulario.
- `function drawCurve(id, history, trainKey, valKey, rate)` — Dibuja entrenamiento y validación por época sin generar datos para modelos sin historia.
- `function drawConfusion(model)` — Muestra la matriz de confusión y las clases del modelo activo.
- `async function auditDataset()` — Solicita la auditoría del perfil y presenta sus problemas de muestras y procedencia.
- `function renderAudit()` — Presenta grabaciones revisables, problemas de calidad y selección administrativa de archivos.
- `async function modifySamples(action)` — Solicita borrar o reasignar muestras confirmadas dentro de una misma lengua.
- `async function loadVersions()` — Consulta las versiones guardadas y sus métricas para el perfil activo.
- `function renderRecognitionDiagnostics(version)` — Explica etapas de rechazo, soporte y separación de reservas de una versión.
- `function renderVersions()` — Muestra modelos y comparaciones y ofrece activación administrativa cuando corresponde.
- `async function exportDataset()` — Solicita un ZIP del perfil activo y lo descarga sin mezclar lenguas.
- `function downloadBlob(blob, name)` — Descarga un recurso generado en memoria y libera después su URL temporal.
- `async function importDataset(event)` — Lee el ZIP elegido y solicita validarlo e incorporarlo al perfil seleccionado.
- `async function previewSample(id)` — Abre el detalle de una toma con metadatos y curvas de movimiento y calidad.

### `static/phone.js`

- `async function phoneApi(route, body = {})` — Envía peticiones móviles con la llave temporal de la sala sin utilizar cuentas del estudio.
- `function phoneError(text)` — Muestra o limpia el error de la página móvil.
- `function drawPhoneMessages(data)` — Actualiza mensajes y borrador solo cuando cambian y lee respuestas recibidas una sola vez.
- `async function pollPhoneState()` — Consulta la sala cuando no se están enviando fotogramas y avisa si dejó de estar disponible.
- `async function phoneFrame()` — Reutiliza el lienzo para enviar un fotograma y mantiene una cadencia objetivo sin peticiones superpuestas.
- `async function startPhone()` — Solicita permiso de cámara y conecta su flujo con la sesión móvil de la sala.
- `async function stopPhone(notify = true)` — Detiene pistas y temporizador y, si corresponde, libera la sesión móvil en el servidor.
- `async function sendPhoneMessage(event)` — Envía el texto escrito a la otra persona y muestra el historial actualizado.
- `async function takePhoneSnapshot()` — Congela una foto en memoria y compara su forma mediante el modo experimental de la sala.

### `static/conversation.js`

- `function conversationRender(data)` — Dibuja mensajes y borradores temporales y anuncia solamente respuestas nuevas de la otra persona.
- `async function conversationPoll()` — Consulta el estado de la sala y limpia la interfaz si vence o deja de estar disponible.
- `function closeConversationUI(message = '')` — Restablece controles y estado vacío conservando una referencia estable al mensaje inicial.
- `async function createConversation()` — Crea una sala con consentimiento y presenta QR y enlace si se configuró HTTPS móvil.
- `async function endConversation()` — Revoca la sala en el servidor y elimina su presentación local.
- `async function sendConversationMessage(event)` — Envía una respuesta escrita y la incorpora al historial compartido.
- `async function publishRecognizedSign(text, confidence)` — Acumula una confirmación de la cámara de computadora en el borrador de su sala.

### `static/accounts.js`

- `async function accountApi(path, body)` — Envía operaciones de cuenta con el CSRF de acceso, separado del token del estado de cámara.
- `function lockAccount()` — Oculta el estudio, detiene la cámara y vuelve a consultar la sesión de acceso.
- `function accountScreen(mode)` — Configura los campos de registro o inicio de sesión del modo autenticado heredado.
- `async function bootstrapAccounts()` — Comparte la carga inicial en curso para evitar consultas de acceso duplicadas.
- `async function loadAccount()` — Abre el estudio en modo local o muestra el acceso del despliegue autenticado.
- `function renderTeam()` — Aplica identidad y permisos y oculta controles de cuentas cuando está activo el modo local.

### `static/continuous.js`

- `class ContinuousCapture` — Mantiene el contador y la identidad de una tanda, incluyendo pausa y descarte de respuestas repetidas.
- `constructor()` — Inicializa una tanda inactiva con contador, límite y conjunto de tomas recibidas.
- `start(limit)` — Valida entre 5 y 60 tomas e inicia una identidad nueva de tanda.
- `complete(id, serial)` — Cuenta una toma completa solo una vez y termina al alcanzar el objetivo.
- `pause()` — Suspende la tanda e invalida su cuenta atrás anterior sin borrar tomas completas.
- `resume()` — Reactiva la programación de tomas conservando contador y objetivo.
- `stop()` — Cancela la tanda e invalida respuestas antiguas conservando el número de tomas completas.
- `current(serial)` — Comprueba si una operación pertenece a la tanda activa y no pausada.

### `static/speech.js`

- `class SenaSpeechQueue` — Gestiona la voz con una cola breve y sin cortar el mensaje que ya está sonando.
- `constructor(synthesis, Utterance, onError = () => {})` — Conserva el sintetizador y prepara la consulta de voces instaladas.
- `enqueue(text, locale)` — Añade un texto no repetido y limita la cola para no acumular retraso de anuncios.
- `playNext()` — Selecciona voz e idioma y reproduce el siguiente mensaje al terminar el anterior.

### `static/rig.js`

- `class RigOverlay` — Mantiene el dibujador auxiliar heredado; la interfaz activa dibuja hand_rig desde app.js.
- `constructor(canvas)` — Vincula el lienzo auxiliar e inicializa preferencia y temporizador.
- `clear()` — Limpia el lienzo y cancela el vencimiento del dibujo auxiliar.
- `setEnabled(enabled)` — Cambia la activación del dibujador auxiliar y retira los puntos antiguos.
- `draw(rig)` — Representa puntos finitos del formato auxiliar cuando está activado.
