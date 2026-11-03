# Seña

Seña es una aplicación local para recopilar ejemplos de lenguas de señas, entrenar modelos con esos datos y reconocer señas en una cámara. También ofrece una sala temporal para conversar desde una computadora y un teléfono.

> Los siete perfiles son **LSM**, **DGS**, **ASL**, **JSL**, **CSL**, **LSF** y **Libras**. Cada perfil conserva su propio vocabulario, dataset y modelos. Tener un perfil disponible no significa que incluya un modelo entrenado: el sistema solo reconoce las clases para las que se grabaron ejemplos y se entrenó un modelo.

## Diagrama del flujo

![Diagrama de flujo de Seña: captura, entrenamiento, reconocimiento y conversación](docs/diagrama_flujo_sena.svg)

El diagrama también está disponible en [SVG](docs/diagrama_flujo_sena.svg), para ampliarlo sin perder calidad.

## Iniciar la aplicación

Requiere el entorno virtual y dependencias del proyecto. Desde la carpeta raíz:

```bash
.venv/bin/python web_app.py
```

Abre [http://127.0.0.1:8765](http://127.0.0.1:8765). Deja la terminal abierta mientras la usas; `Ctrl+C` apaga el servidor. Si el puerto ya está ocupado, la aplicación normalmente ya está ejecutándose. Puedes elegir otro con:

```bash
.venv/bin/python web_app.py --port 8877
```

La página funciona en modo local sin iniciar sesión. Para enlazar temporalmente un teléfono a través de Tailscale Serve, el servidor debe seguir escuchando en localhost y arrancarse con el origen HTTPS privado:

```bash
.venv/bin/python web_app.py --phone-origin https://NOMBRE-DE-TU-MAC.tailnet.ts.net
```

El teléfono también debe estar conectado a la red Tailscale. La cámara del navegador requiere HTTPS, por eso se usa el origen de Tailscale para abrir la página móvil. La conversación dura una hora; los mensajes se guardan solo en memoria y se descartan al cerrar o vencer la sala. No configures Funnel ni expongas el puerto directamente a Internet. La guía heredada de acceso privado está en [docs/ACCESO_PRIVADO.md](docs/ACCESO_PRIVADO.md); para el flujo actual del teléfono, consulta [docs/CAMARA_TELEFONO.md](docs/CAMARA_TELEFONO.md).

## Secciones de la aplicación

- **Inicio:** resumen de los perfiles, ejemplos, actividad y modelos existentes.
- **Reconocimiento:** cámara, detección de calidad, predicciones, confianza, estabilidad e historial. La opción de voz usa la síntesis disponible en el navegador.
- **Conversación:** crea una sala para intercambiar texto o señas entre la computadora y el teléfono. Las letras reconocidas se acumulan y se envían tras una pausa sin una seña nueva.
- **Dataset:** vocabulario, alfabetos, ejemplos, revisión, grabaciones consecutivas e importación/exportación. Las tandas pueden ser de 5 a 60 tomas; para entrenar se necesitan al menos 30 ejemplos completos por clase y dos clases distintas. Se recomiendan 30–60 tomas variadas por clase.
- **Entrenamiento:** estrategias, épocas, progreso, métricas, confusiones, versiones y selección del modelo activo. La reserva de prueba no se debe usar para ajustar el entrenamiento.
- **Configuración:** selección de cámara, apariencia y opciones de reconocimiento. El botón «Rig de manos» de la esquina superior derecha de la cámara activa una superposición temporal que deja ver dónde detecta las manos. También puedes cambiarlo en Configuración; el rig es solo visual y no modifica el modelo.

## Cómo se recopilan y guardan los datos

1. Selecciona el perfil de lengua de señas y la cámara.
2. En Dataset, elige una clase existente o registra el nombre de una seña nueva.
3. Espera a que el encuadre y las manos pasen las comprobaciones de captura.
4. Realiza una seña completa durante cada toma. Para señas con movimiento, muestra el recorrido entero desde el inicio hasta el final.
5. Guarda las tomas en la clase correspondiente. Las tomas sin etiqueta permanecen pendientes hasta nombrarlas o descartarlas.

La captura de entrenamiento guarda secuencias de landmarks y metadatos de sesión, no video ni audio. Los datos están bajo `web_data/`; los ejemplos de cada perfil se mantienen separados. La aplicación no verifica que la forma de la seña sea lingüísticamente correcta: revisa las tomas antes de usarlas.

La cámara del teléfono transmite imágenes al servidor local de la computadora para extraer landmarks mientras se reconoce. Las imágenes se procesan en memoria y no se archivan como video o fotos. Si activas el rig, la interfaz dibuja sobre el fotograma procesado la detección de manos; no se guarda esa superposición. En una conversación, el texto y las señas reconocidas se mantienen en memoria hasta que termina la sala.

## Qué hace el entrenamiento

El entrenamiento lee ejemplos etiquetados, comprueba su forma y procedencia, crea particiones por sesiones/personas cuando hay metadatos suficientes y mantiene apartada la prueba. A partir de las secuencias calcula las características configuradas y ajusta una red temporal. La validación calibra los criterios de aceptación; después se calcula la evaluación de prueba. Las versiones, metadatos y curvas se conservan bajo `models/<perfil>/` y `web_data/`.

Las estrategias disponibles son `baseline`, `discriminative`, `contrastive`, `trajectory` y `robust`. No todas tienen por qué mejorar con cualquier dataset. Compara las métricas por clase y las confusiones, no solo el accuracy agregado. Las tomas consecutivas de una misma persona o sesión no demuestran generalización a personas nuevas; para comprobarlo, graba sesiones independientes con diferentes participantes.

Las mejoras recientes de características y de rechazo pueden requerir volver a entrenar para que el modelo use esas características. Los bundles y datasets anteriores se conservan para compatibilidad, pero un modelo antiguo no adquiere por sí solo nueva información aprendida.

## Dos formas de probar

### Reconocimiento temporal (modo normal)

El sistema analiza secuencias de landmarks a lo largo del tiempo. La forma de dedos, la posición relativa y la trayectoria ayudan a diferenciar señas estáticas y con movimiento. Solo confirma cuando la salida es suficientemente estable y supera los controles de confianza, ambigüedad, forma y movimiento calibrados para ese modelo. Si falta evidencia, puede rechazar en lugar de inventar una clase.

En el modo de prueba, una puntuación de 90% o superior puede satisfacer el umbral de confianza, pero sigue necesitando tres ventanas estables y pasar los demás controles. Ese valor es una regla de la interfaz de prueba, no una garantía de que la predicción sea correcta.

### Foto experimental

La foto experimental compara una sola postura de mano con referencias geométricas del modelo y solo confirma clases con soporte suficiente en validación. No usa la red temporal como si la imagen fuera una secuencia, no reconoce movimientos ni gramática y no entrega una probabilidad comparable con la confianza normal. Para una seña dinámica, usa reconocimiento temporal. Detalles en [docs/FOTO_EXPERIMENTAL.md](docs/FOTO_EXPERIMENTAL.md).

## Mapa del código

| Archivo o carpeta | Función |
|---|---|
| `web_app.py` | Servidor HTTP local, sesiones de cámara, endpoints, conversación, inferencia y arranque. |
| `sign_languages.py`, `config.py`, `alphabets.py` | Perfiles, rutas, contrato de captura, etiquetas y alfabetos. |
| `web_dataset.py`, `data_collection.py` | Lectura/escritura de ejemplos, tomas pendientes y captura de secuencias. |
| `capture_quality.py` | Calidad de encuadre, landmarks, secuencia y región de la mano. |
| `recognition_features.py`, `motion_features.py` | Características versionadas de manos/cuerpo y trayectoria temporal. |
| `recognition_decision.py`, `recognition_analysis.py` | Umbrales, evidencia, rechazo, métricas y análisis de confusiones. |
| `snapshot_recognition.py` | Comparación experimental de postura en una imagen. |
| `dataset_tools.py`, `validation_protocol.py` | Auditoría, intercambio, deduplicación y separación por grupos. |
| `model.py`, `web_train.py`, `train.py`, `discriminative_learning.py` | Arquitectura, entrenamiento, estrategias y evaluación. |
| `studio_services.py`, `admin_auth.py`, `team_access.py`, `accounts.py` | Versiones, operaciones protegidas y componentes heredados del modo de equipo. |
| `private_server.py`, `deploy/` | Utilidades heredadas para acceso privado/proxy. El uso local no requiere login. |
| `static/index.html`, `static/styles.css` | Estructura y estilos de la página. |
| `static/app.js`, `static/continuous.js`, `static/studio.js` | Cámara, captura continua, navegación y panel de datos/entrenamiento. |
| `static/conversation.js`, `static/phone.html`, `static/phone.js` | Sala de conversación y vista móvil. |
| `static/speech.js`, `static/rig.js`, `static/accounts.js` | Voz, visualizador de depuración y compatibilidad de cuentas. |
| `tests/` | Pruebas automatizadas de utilidades, servidor, interfaz y flujos de reconocimiento. |
| `docs/FUNCIONES.md` | Catálogo de funciones y métodos Python/JavaScript con explicación breve. |
| `docs/` | Guías de teléfono, validación, precisión, modo experimental y decisiones técnicas. |

Los comentarios en el código explican las funciones, clases y utilidades de prueba junto a su definición. El catálogo completo está en [docs/FUNCIONES.md](docs/FUNCIONES.md). `main.py`, `train.py` y `data_collection.py` también conservan el flujo de escritorio heredado; la interfaz web actual se inicia con `web_app.py`.

## Pruebas automatizadas

Para ejecutar la suite Python:

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest discover -s tests -v
```

Algunas pruebas de interfaz usan Node.js:

```bash
node tests/test_continuous.js
node tests/test_cameras.js
node tests/test_studio_ui.js
```

Las pruebas de entrenamiento usan modelos y datos sintéticos en ubicaciones temporales, no deberían añadirse al dataset real.

## Límites que conviene tener presentes

- No hay modelos preentrenados completos para las siete lenguas ni traducción automática de cualquier conversación. El vocabulario traducido es texto de salida; cada perfil requiere sus propios ejemplos y entrenamiento.
- Más ejemplos ayudan solo si son correctos y variados. La evaluación con pocas sesiones no prueba rendimiento en la vida diaria.
- La detección depende de una cámara, iluminación, distancia y manos visibles suficientes. La función de recuperación de seguimiento no elimina todas las pérdidas de MediaPipe.
- La síntesis de voz depende de las voces instaladas en el navegador/dispositivo.
- El rig es una herramienta visual de depuración; no mejora por sí mismo el modelo.
