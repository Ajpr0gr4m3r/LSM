# Comparar una foto de una seña

Este modo experimental compara una única imagen con las formas de mano aprendidas por el modelo activo. Sirve para probar posturas estáticas. Una imagen no contiene trayectoria ni permite saber qué movimiento se hará después; las clases detectadas como dinámicas no se confirman por foto.

## Cómo usarlo

1. En Reconocimiento, activa la cámara y selecciona **Foto experimental · señas estáticas**.
2. Haz la postura con los dedos visibles y pulsa **Comparar una foto**.
3. La imagen que se comparó permanece visible. Se muestra el resultado o la razón del rechazo.
4. Desmarca Foto experimental para volver al reconocimiento temporal.

En el teléfono están disponibles la misma casilla y el botón después de activar la cámara de la sala. Una foto confirmada entra al borrador de conversación y se envía después de la pausa habitual.

Mientras el modo de foto está activo, los fotogramas de vista previa comprueban el encuadre y no generan predicciones temporales. La comparación utiliza una detección independiente de la imagen, sin arrastrar el seguimiento de los fotogramas anteriores. La imagen permanece en memoria; no se guarda en el dataset ni en archivos.

## Qué se compara

Se reutiliza la mitad estática (medianas) de las referencias del filtro de manos del modelo activo. Las referencias proceden del entrenamiento. No se alimenta una imagen repetida a la red temporal para aparentar una secuencia.

La distancia se calibra de forma separada para este experimento con una observación real central de cada grabación de la reserva de validación del modelo activo. Los hashes de entrenamiento y prueba se excluyen; los duplicados no aumentan el soporte. Se exige soporte mínimo y se rechazan distancias fuera de rango o formas demasiado próximas a varias clases.

Se comparan forma local, flexión y orientación según la versión del descriptor guardado. No es traducción gramatical ni un clasificador completo de expresiones faciales o posiciones respecto al cuerpo. Solo incluye el vocabulario del modelo activo; añadir una etiqueta al dataset no la enseña a este modo.

Los valores internos son distancias geométricas, no probabilidades neuronales. Los resultados se muestran sin inventar un porcentaje de confianza. Los límites se ajustaron sobre validación, por lo que su desempeño sobre esos mismos ejemplos no es una evaluación independiente de precisión. No se usó la prueba reservada para ajustar este experimento.

## Soporte en el modelo actual al preparar el experimento

Se pudieron preparar filtros de foto para A, B, C, D, E, F, G e I. H no reunió suficiente soporte fiable en esa validación y J se excluyó por movimiento. Este listado depende de la versión activa y puede cambiar con un nuevo entrenamiento. No implica una medición de precisión con fotos nuevas.

## Seguimiento temporal

Se corrigió el control de iluminación/enfoque para inspeccionar el área de las manos en las mismas coordenadas reflejadas de MediaPipe. Antes, un fondo oscuro o sin textura podía rechazar una mano bien iluminada.

Si el seguimiento pierde una mano válida recientemente, se permite una re-detección independiente del mismo fotograma, como máximo una vez por segundo. Solo se utiliza si encuentra landmarks válidos; no se rellenan manos ausentes con coordenadas anteriores. Si se recupera, se reinicia el rastreador de video. La captura de dataset y la inferencia comparten este comportamiento.

Las pruebas verifican forma estática, rechazo de movimiento y ambigüedad, soporte insuficiente, independencia del detector de foto, validación sin duplicados, fondo oscuro, recuperación sobre el mismo fotograma, autenticación y flujo del teléfono. Falta comprobar la estabilidad y precisión con cámaras y fotos nuevas de personas reales.
