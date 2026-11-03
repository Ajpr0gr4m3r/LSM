# Contador y entrenamiento de letras — 27 de octubre de 2026

## Cambios

- Contador `completas/objetivo` en la esquina superior derecha de la cámara durante
  la tanda y al detenerla. No cuenta respuestas duplicadas ni tomas incompletas.
- Preprocesamiento versionado `stable-finger-geometry-v4`: 650 entradas, incluidos
  30 valores de extensión y separación de dedos. Mantiene los canales anteriores.
  Entrenamiento e inferencia usan la misma función. Las versiones antiguas conservan
  sus dimensiones y su preprocesamiento original.
- Variantes generadas en landmarks crudos, con características derivadas después;
  sin modificar independientemente coordenadas y geometría del mismo ejemplo.
- Filtro contrastivo de forma: compara la clase propuesta con las otras clases,
  con tolerancias elegidas en validación. Puede abstenerse aunque softmax sea alto.
- Mejor época por F1 macro y recuperación de la peor clase, con pérdida como
  desempate; activación exige mínimos por clase además de métricas globales.
- Particiones equilibradas por clase sin dividir sesiones/personas; al menos 40%
  de los ejemplos de cada clase se reservan para entrenar. Los históricos sin
  procedencia siguen siendo una limitación explícita, nunca se inventa su origen.
- Interfaz muestra vocabulario realmente aprendido, letras pendientes y métricas
  por clase. No se añaden dibujos de landmarks ni se guardan videos.

## Entrenamientos reales

1. `4b521c2413fc45eda92896cca5b8387c`: A–H, 634 ejemplos, 21 épocas ejecutadas.
   Guardado sin activar. D tuvo 0/30 aciertos en validación y ninguna confirmación.
   Sus ejemplos se conservaron; necesitan revisión y nuevas sesiones variadas.
2. `d75ccf444ae94ef0b495431fada45cf6`: vocabulario previamente activo A, B, C, E,
   F, G más H. 572 ejemplos, particiones 400/86/86, 19 épocas ejecutadas de máximo
   60. Activado por los criterios de validación: F1 macro 0,9424, 70/86 aceptados,
   todos correctos. El test se consultó después de elegir la época y calibrar filtros.

Prueba reservada del modelo activo: 57/86 aciertos sin rechazo (66,3%);
53/86 aceptados por los filtros (61,6% de cobertura), los 53 correctos.
**No equivale a 100% de reconocimiento ni demuestra mejora con nuevos usuarios.**

| Letra | Tomas de prueba | Aciertos sin filtro | Confirmaciones correctas | Rechazadas |
|---|---:|---:|---:|---:|
| A | 8 | 8 | 8 | 0 |
| B | 5 | 5 | 4 | 1 |
| C | 9 | 9 | 7 | 2 |
| E | 5 | 5 | 5 | 0 |
| F | 10 | 10 | 10 | 0 |
| G | 10 | 10 | 10 | 0 |
| H | 39 | 10 | 9 | 30 |

H todavía generaliza mal entre las sesiones reservadas: 29/39 H se clasificaron
como G antes del filtro, pero ninguna de esas confusiones fue aceptada. Esto
justifica recoger/revisar H y G en sesiones diferentes, con cambios moderados de
posición, distancia y orientación; más repeticiones idénticas no solucionan el
problema. B/E no se confundieron en los diez ejemplos de prueba disponibles, una
muestra demasiado pequeña para asegurar que el problema desapareció en uso real.

El modelo anterior `6f91a4f122644d4bb6a3144893b573f3` sigue guardado y se comprobó
que carga y produce seis probabilidades finitas con su preprocesamiento v2.
No se comparan porcentajes de ambos modelos como si compartieran vocabulario/test.

## Pruebas

- 62 pruebas Python aprobadas (incluye entrenamiento/serialización sintéticos,
  captura, inferencia, compatibilidad, grupos, geometría y rechazo entre clases).
- Cuatro suites Node aprobadas: tandas, cámaras, contrato UI y contador.
- Sintaxis JavaScript comprobada; navegador sin errores de consola. La interfaz
  muestra A, B, C, E, F, G, H en el modelo activo.
- Inferencia real del nuevo modelo por `Runtime.load_model` verificada con las
  86 tomas reservadas. No se realizó una prueba gestual humana en cámara durante
  esta actualización. Los resultados son por clip; no una evaluación de streaming.

Referencias de las APIs utilizadas: [21 landmarks de MediaPipe](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/drawing_styles/hand_landmarker/HandLandmark),
[selección de checkpoint de Keras](https://keras.io/api/callbacks/model_checkpoint/).
Estas referencias documentan las APIs; las métricas anteriores proceden del dataset
local, no de esos sitios.
