> **Actualización: cuentas y equipo compartido.** La página ahora requiere iniciar
> sesión. La primera cuenta administradora se crea desde localhost con usuario y contraseña nuevos; los demás usuarios entran por invitación. Consulta [Usuarios y alojamiento](docs/EQUIPO.md).
> Los ejemplos guardados se comparten entre cuentas del mismo servidor. Las cámaras
> envían imágenes al servidor para procesarlas en memoria; solo se guardan puntos.
> Las referencias al modo local de las secciones históricas describen el funcionamiento
> en localhost; para acceso remoto usa la configuración HTTPS de la guía.

# Seña · Estudio local

Aplicación para capturar ejemplos, gestionar datasets y entrenar/reconocer **señas
individuales**. Procesamiento local, siete perfiles independientes y compatibilidad
con los datasets NPZ y bundles Keras anteriores. No incluye siete modelos
preentrenados ni traducción de conversaciones libres.

## Ejecutar

Desde esta carpeta, con el entorno Python 3.11 existente:

```bash
.venv/bin/python web_app.py
```

Abre http://127.0.0.1:8765. Mantén la Terminal abierta. Ctrl+C detiene el servidor.
Para usar otro puerto: `.venv/bin/python web_app.py --port 8877`.
Si el puerto está ocupado, usa la instancia ya abierta o detén la anterior antes
de iniciar otra. Tras actualizar código Python, reinicia el servidor y recarga la página.

## Cinco áreas

- **Inicio:** estadísticas reales de los siete perfiles, modelos activos, tomas pendientes y actividad reciente.
- **Reconocimiento:** cámara en espejo, calidad del encuadre, confirmación estable, alternativas orientativas, historial, voz disponible en el navegador y exportación JSON de la sesión.
- **Dataset:** grabación individual o tandas de 5–60, cuenta atrás, nombres después de capturar, vocabulario Unicode, abecedarios, búsqueda, revisión por archivo e importación/exportación ZIP.
- **Entrenamiento:** selección de clases, épocas, progreso, curvas persistentes, matriz de confusión, precisión/recuperación/F1, versiones y activación administrativa de versiones anteriores.
- **Configuración:** detección/selección de cámara, apariencia clara/oscura/sistema, reducción de movimiento y confirmación estricta opcional. La interfaz permanece en español; cada perfil tiene su idioma de salida propio.

La fuente Manrope y los SVG Lucide se sirven desde `static/vendor/`. No hay CDN,
telemetría ni peticiones a terceros durante el uso. Se retiró el rig de la interfaz
y del protocolo activo conforme al requisito actual. No se muestran esqueletos
ni puntos sobre la cámara; tampoco hay lecciones ni ejercicios educativos.

## Captura de calidad

1. Selecciona la lengua real: LSM, DGS, ASL, JSL, CSL, LSF o Libras.
2. Elige la cámara en Configuración y actívala desde Reconocimiento o Dataset.
3. En Dataset puedes asignar un identificador opcional de participante, sin nombres personales.
4. Graba una toma o una tanda. La captura espera manos visibles y buen encuadre;
   no comienza a acumular cuadros mientras las manos estén fuera del encuadre.
5. Haz la seña completa durante la toma y mantén los dedos visibles. Se rechazan
   nuevas tomas con más del 20 % de cuadros insuficientes. El análisis de luz y
   enfoque es orientativo: no demuestra que el gesto o su etiqueta sean correctos.
6. Pon nombre y guarda. Repetir el nombre suma otro ejemplo. Las tomas completas
   quedan pendientes si se detiene una tanda; la toma parcial se descarta.

No se guardan video, audio ni fotos. Se guardan **30 cuadros de puntos** con los
metadatos de procedencia. Estos datos también representan movimientos personales:
trátalos como datos privados al exportarlos. La captura mantiene clips de 30 cuadros para conservar el contrato de los modelos;
la espera por encuadre no es un segmentador lingüístico universal. Se avisa si
termina con movimiento marcado para revisar posibles recortes. La revisión por toma muestra curvas
escalares de movimiento/calidad y sus metadatos, sin reconstruir un esqueleto.

## Datos y separación de evaluación

Se requieren **30 ejemplos completos por clase**, al menos **dos clases** y se
recomiendan **30–60 ejemplos variados**. Elegir 5 tomas solo determina el tamaño de
una tanda, no reduce el mínimo para entrenar. Puedes seleccionar las clases listas
y dejar fuera las que todavía estás preparando.

Nuevas tomas conservan `session_id`, `batch_id`, participante opcional y un hash
corto del identificador de cámara. El identificador de cámara en claro no se guarda.
El commit desde tomas pendientes conserva la procedencia.

- Con participante registrado, **todos sus ejemplos permanecen en el mismo conjunto**.
- Sin participante, se agrupa la sesión completa; una tanda no se divide entre conjuntos.
- Copias exactas se vinculan en el mismo grupo, incluso si aparecieron en sesiones distintas.
- Ejemplos idénticos con etiquetas distintas bloquean el entrenamiento.
- Cada clase debe aparecer en entrenamiento, validación y prueba. Si eso es imposible,
  se pide grabar en al menos tres grupos independientes. No se recurre a separar
  arbitrariamente la misma tanda para conseguir una puntuación favorable.
- En archivos históricos sin procedencia se agrupan copias exactas por su hash,
  pero **no se puede probar independencia entre personas o tandas**. Se advierte
  tanto en los metadatos como en la interfaz. No se inventa esa información.

Registra correctamente los participantes: abrir tres veces la cámara con la misma
persona no equivale a evaluar tres personas independientes.

## Reconocimiento y entrenamiento

La BiLSTM compacta se conserva: una arquitectura más grande no tiene una mejora
medida que justifique más recursos. Entrenamiento e inferencia comparten funciones
y seleccionan el preprocesamiento por la versión guardada en cada modelo.

Los **nuevos entrenamientos** usan `stable-finger-geometry-v4` (650 entradas por cuadro):
filtrado causal leve sin rellenar manos ausentes, normalización corporal, forma de
manos relativa a palma/muñeca y normalización facial local cuando hay referencia
ocular suficiente. Conserva el orden temporal y no refleja manos. El filtro nuevo
de rechazo usa forma y trayectoria temporal, incluida la muñeca en el marco corporal.
Añade 30 medidas de extensión y separación de dedos, calculadas de los mismos
landmarks durante entrenamiento e inferencia. El rechazo contrasta la clase
predicha con las demás: una coincidencia más cercana con otra clase no se confirma.

Las pequeñas variaciones de cámara y ruido se crean **después** de separar los datos
y solo sobre entrenamiento. La normalización estadística se calcula solo con el
entrenamiento original. Las variantes se generan sobre los puntos crudos y después
se recalculan todas las características, evitando geometría incoherente. Validación ajusta confianza y margen; la estabilidad de
cinco predicciones es una regla conservadora de ejecución, no una cifra validada
con conversaciones reales. La prueba queda fuera del ajuste.

Se rechazan candidatos ambiguos o alejados de las referencias. Se muestra una
confirmación por gesto y se espera bajar las manos para iniciar otro. Inferencia
limitada a aproximadamente 5 evaluaciones por segundo mientras se procesan cuadros
a la frecuencia de captura. Referencias del filtro precargadas y consultas de dataset
cacheadas reducen trabajo repetido.

La mejor época se elige con 70% F1 macro y 30% recuperación de la peor clase
en validación; la pérdida desempata. No se usa el test para elegir épocas.
El reparto busca equilibrio por clase y conserva al menos el 40% de cada clase
para entrenamiento, sin dividir sesiones ni participantes.

La activación de un nuevo modelo exige F1 macro de validación >= 0,8, precisión de
predicciones aceptadas >= 0,95 y cobertura >= 0,5. Además, cada letra necesita
recuperación >= 0,6, al menos 2 predicciones aceptadas, precisión aceptada >= 0,9
y cobertura >= 0,25 en validación. Estas cifras son criterios de aceptación, no
garantías estadísticas con muestras pequeñas. Cuando hay una validación común
independiente documentada, además no puede empeorar accuracy, F1, precisión aceptada
ni cobertura frente al modelo previo. Si falta la trazabilidad del modelo histórico,
no se presentan sus porcentajes como comparaciones equivalentes. Se guardan los
hashes de cada partición para futuras comparaciones. Los modelos que no superan
los criterios se guardan sin activar.

Estos controles **no garantizan rechazo perfecto de todas las señas desconocidas**.
No hay un corpus independiente de negativos ni una evaluación clínica o de uso
cotidiano. Las puntuaciones pequeñas del dataset propio no prueban generalización.
Usa grabaciones nuevas, otras personas, cámaras, días y ángulos para comprobarlo.
La falta de manos o el mal encuadre reinicia la observación para no unir gestos separados.

## Compatibilidad y versiones

- Se conservan las entradas históricas crudas, `body-relative-v1`, `body-hand-relative-v2` y `stable-body-hand-v3`.
- No se modifican pesos, vocabularios ni archivos de ejemplos durante la actualización.
- Los nuevos filtros de preprocesamiento/guardia temporal requieren volver a entrenar.
  El diseño, revisión, calidad de captura y control de confirmaciones no lo requieren.
- Los modelos viejos sin historia de épocas muestran un aviso, no gráficas simuladas.
- Activar una versión anterior exige la contraseña administrativa, comprobar su
  serialización/dimensiones y al menos 30 ejemplos por cada clase. Así no se reactiva
  silenciosamente una D u otra clase cuyos ejemplos se borraron.
- Los scripts originales de escritorio (`main.py`, `train.py`, `data_collection.py`)
  y su dataset se conservan; sus detalles están en `docs/LEGACY.md`.

## Administración e intercambio

La contraseña administrativa existente se conserva en `web_data/admin/auth.json`
como PBKDF2 con sal; no aparece en los archivos estáticos ni se guarda en el navegador.
Las rutas administrativas comprueban la contraseña en el servidor y mantienen el
límite de intentos. Exportar o revisar no requiere contraseña; eliminar, reasignar
muestras y activar modelos sí. Todas las mutaciones usan control de origen/token local.

Puedes retirar toda una clase o seleccionar archivos. Los retirados pasan a
`web_data/trash/<lengua>/<operación>/`; se guarda un registro. Las reasignaciones
permanecen dentro de la misma lengua y registran sus etiquetas originales. Al
modificar ejemplos de una clase entrenada, su modelo se desactiva hasta reentrenar.
Para recuperar archivos retirados manualmente, detén el servidor y cópialos desde
la carpeta de recuperación a su carpeta de dataset original. La protección web no
impide que alguien con acceso al sistema de archivos modifique datos directamente.

Exportación ZIP `sena-dataset-v1`: incluye manifiesto, perfil/pipeline, nombres,
identificadores y ejemplos NPZ válidos con procedencia. No incluye modelos,
contraseñas ni archivos inválidos. Importación valida todos los ejemplos antes de
escribir, rechaza otra lengua/configuración, rutas inseguras, ZIP expansivos y
etiquetas en conflicto; omite duplicados exactos. Límites: 32 MB comprimidos,
128 MB expandidos y 2000 ejemplos por paquete. No se usa `pickle` ni `extractall`.

## Archivos principales

| Archivo | Responsabilidad |
|---|---|
| `web_app.py` | HTTP local, sesiones, captura e inferencia |
| `capture_quality.py` | Encuadre, integridad de manos, luz y enfoque |
| `recognition_features.py` | Preprocesamientos versionados y filtros de rechazo |
| `web_dataset.py` | Persistencia compatible y tomas pendientes |
| `dataset_tools.py` | Auditoría, intercambio, procedencia y particiones por grupos |
| `studio_services.py` | Versiones, actividad y operaciones administrativas |
| `web_train.py` | Entrenamiento aislado, calibración, métricas e historia |
| `static/app.js` | Controlador de cámara y capturas |
| `static/studio.js` | Navegación, dashboard, revisión, gráficas y versiones |

La auditoría previa y decisiones están en `docs/AUDITORIA.md`; las licencias de
assets se conservan en `docs/THIRD_PARTY.md`.

## Pruebas

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest discover -s tests -v
node tests/test_continuous.js
node tests/test_cameras.js
node tests/test_studio_ui.js
```

Las pruebas de entrenamiento crean modelos sintéticos solo en carpetas temporales;
no añaden ejemplos artificiales al dataset real ni sustituyen los modelos del usuario.


### Contador de la tanda

En Dataset, el contador superior derecho de la cámara muestra `completas/objetivo`
(por ejemplo `30/60`). Avanza solo al recibir una toma completa; las respuestas
repetidas, cuentas atrás o capturas fallidas no suman. Conserva el valor al detener
la tanda y se reinicia al empezar otra. Las tomas siguen pendientes de nombrar y
guardar; son secuencias de puntos, no archivos de video.
