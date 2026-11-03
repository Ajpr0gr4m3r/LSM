# Distancia, dedos y movimiento

Se añadió la estrategia experimental **Distancia, dedos y movimiento** (`robust`). Utiliza la arquitectura temporal y los canales `articulation-motion-v5` existentes. No cambia las entradas de los modelos guardados.

## Cambios

- Captura con un límite de 640 × 480 píxeles, conservando la proporción, y JPEG de calidad 0.82. El resultado depende de la resolución real que entregue la cámara. No se reconstruyen detalles que la cámara no capta.
- El teléfono intenta mantener la misma cadencia de 10 fotogramas/s de la captura de entrenamiento, con una petición a la vez. Una conexión o inferencia lenta todavía puede reducirla. Se eliminó el intervalo fijo de 150 ms.
- La estrategia nueva combina variaciones temporales ordenadas, escala del firmante de 0.72 a 1.12 y ruido leve proporcional a la palma. Las variantes se generan solo después de separar entrenamiento, validación y prueba. Conserva las nueve secuencias totales por ejemplo del entrenamiento anterior.
- El filtro de manos versionado `finger-articulation-v3` añade ángulos articulares y orientación de palma a la forma local y flexión de dedos. La misma extracción se ejecuta en calibración e inferencia. La trayectoria mantiene el filtro `trajectory-v2`, que distingue el orden y la dirección del movimiento.
- Se mantienen calibración, rechazo de ambigüedad, comparación con la versión anterior y las reservas históricas. No hay reglas por nombre de letra ni cambios de umbral para E/B.

## Uso

En Entrenamiento, selecciona **Distancia, dedos y movimiento · experimental**. Graba ejemplos cercanos y a la distancia real de uso, con los dedos enfocados y el recorrido completo. Cada clase necesita sesiones independientes para entrenamiento, validación y prueba.

El detalle de captura y la cadencia móvil se aplican al recargar la página. Para utilizar los filtros y aumentos nuevos hace falta volver a entrenar con la estrategia nueva. Los modelos anteriores siguen usando sus descriptores originales.

## Verificación y límites

Las pruebas verifican invariancia de escala sobre manos sintéticas, separación de flexión, conservación de manos ausentes, dirección temporal, compatibilidad del descriptor histórico, decisiones y carga de scripts. Un entrenamiento mínimo sintético comprobó guardado y carga del paquete nuevo.

Estas pruebas no son una evaluación de precisión con personas ni demuestran una reducción de confusiones E/B. No se entrenó ni activó un candidato con el dataset del usuario durante este cambio. La mejora debe medirse con la evaluación reservada y con nuevas sesiones reales; la versión anterior se conserva.
