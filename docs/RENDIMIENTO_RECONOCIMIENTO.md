# Respuesta de cámara y grabación

## Optimizaciones

- El modelo y sus metadatos permanecen en memoria. Antes de reutilizarlos se comprueban las firmas de `current.json`, `metadata.json` y `model.keras`. Cambiar, desactivar o borrar un artefacto invalida la caché.
- Las peticiones de fotogramas pueden reutilizar conexiones HTTP/1.1. Las respuestas de error cierran la conexión para no reutilizar solicitudes con cuerpos pendientes. TCP_NODELAY evita retrasos por agrupación de paquetes pequeños.
- Los lienzos se reutilizan y solo cambian de tamaño cuando cambia la resolución. Se conservan 640 × 480 como máximo y JPEG 0.82.
- El teléfono actualiza las burbujas solo cuando cambian mensajes, borradores o idioma.
- El preprocesamiento v5 calcula el suavizado una vez, conservando exactamente los valores anteriores.
- La siguiente cuenta atrás de una tanda ya no espera a que termine una consulta completa del inventario. Las tomas se siguen guardando antes de avanzar y el inventario se actualiza periódicamente, al pausar y al finalizar.
- Las tomas individuales permiten elegir 1, 3 o 5 segundos de preparación. El valor inicial es 1 segundo. La pausa entre tomas de una tanda sigue siendo configurable.

## Verificación

Sobre el modelo activo de esta instalación se midieron 80 llamadas de lectura completa de metadatos frente a la comprobación de caché: medianas de 72.525 ms y 0.011 ms respectivamente. Esta comparación mide solo la carga de metadatos; no equivale a una medición de latencia completa ni de fotogramas por segundo.

Las pruebas verificaron invalidación de caché, reutilización de conexión, cierre ante rechazo HTTP, equivalencia exacta del preprocesamiento, reutilización de lienzo, captura, mensajes, tandas y decisiones de reconocimiento.

Se mantienen las secuencias de 30 fotogramas a una cadencia objetivo de 10/s, los filtros de calidad, confianza, ambigüedad, trayectoria y estabilidad. No requiere reentrenamiento. La resolución de cámara, la red y la capacidad de la Mac siguen condicionando la latencia real.

## Corrección de estabilidad

Se recuperó el límite de captura de 640 × 480 para reducir carga tras reportarse inestabilidad en vivo. El rig dibuja la imagen exacta analizada junto con sus puntos, en vez de superponerlos al video que ya avanzó. Las primeras confirmaciones al 90 % requieren tres observaciones consecutivas; las transiciones conservan el requisito de estabilidad del modelo (con mínimo de tres). No cambia el preprocesamiento de los pesos guardados. Las pruebas no demuestran precisión en vivo; hay que verificar la recuperación con la cámara real.
