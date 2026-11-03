# Auditoría previa — Seña

Fecha: 27 de octubre de 2026. Se revisaron todos los módulos Python, controladores
web, perfiles, persistencia, arquitectura, scripts de escritorio y pruebas.

## Arquitectura y compatibilidad
- Servidor HTTP local estándar, MediaPipe Holistic 0.10.14, TensorFlow 2.15 y Python 3.11.
- 7 perfiles aislados; vocabulario Unicode; capturas NPZ sin imagen/audio; borrado recuperable y autenticación PBKDF2 en servidor.
- Tres variantes de entrada existentes: cruda, body-relative-v1 y body-hand-relative-v2. Se conservarán sus reglas exactas y los bundles .keras inmutables.
- BiLSTM compacta sobre secuencias de 30 fotogramas; guardia de forma, confianza y estabilidad. No hay evidencia suficiente para reemplazar la arquitectura por una red más costosa.
- El programa de escritorio usa otro flujo y otro archivo de modelo. No se migrarán sus datos de manera implícita.

## Hallazgos
1. División aleatoria por toma: no garantiza independencia de tandas/personas; los archivos históricos no contienen esa información.
2. Ausencia de auditoría por archivo, importación/exportación y restauración de versiones en la página.
3. Candidatas de baja confianza visibles como palabras grandes; parecen detecciones aunque no se confirmen.
4. Captura de longitud fija sin indicador de encuadre, iluminación ni desenfoque; secuencias con solo pose podían pasar validación histórica.
5. El reinicio del servidor pierde el seguimiento del job. No hay historial de curvas por época persistido en bundles antiguos.
6. Rig solicitado antes: se retirará de la interfaz y del protocolo activo conforme a la instrucción actual. Los módulos previos se conservan como archivos de compatibilidad, sin cargarse.
7. Restablecer un modelo antiguo podría reactivar una seña eliminada: se necesita validación del dataset y registro administrativo.

## Criterio de implementación
- No modificar los ejemplos/modelos actuales ni afirmar mejoras porcentuales sin evaluación.
- Nuevos controles de calidad y rechazo antes de confirmar; resultados ambiguos separados de la predicción confirmada.
- Procedencia opcional de participante, sesión y tanda para capturas nuevas; agrupación estricta donde existe; advertencia honesta para históricos.
- Duplicados unidos en el mismo grupo; aumento únicamente tras separar los conjuntos.
- Nuevas mejoras de preprocesamiento versionadas y compartidas por entrenamiento/inferencia. Nunca reinterpretar un modelo guardado.
- Diseño local sin CDN, analítica ni cargas de video/audio. Navegación en cinco áreas y tema oscuro persistente.

## Referencias consultadas
- MediaPipe Holistic (coordenadas y visibilidad): https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/holistic.md
- Scikit-learn, validación con grupos independientes: https://scikit-learn.org/stable/modules/cross_validation.html
- TensorFlow, regularización y sobreajuste: https://www.tensorflow.org/tutorials/keras/overfit_and_underfit
- Aumento solo en entrenamiento: https://www.tensorflow.org/tutorials/images/data_augmentation
