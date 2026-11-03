# Evaluación de Seña — 28 de octubre de 2026

Ensayo exploratorio con 634 secuencias de LSM y ocho clases, 20 épocas máximas por alternativa y semilla 42. Misma reserva y mismo protocolo de calibración; el conjunto de prueba no seleccionó checkpoints. No se reemplazó el modelo activo.

Partición: 443 entrenamiento, 105 validación, 86 prueba. Se aplicaron aumentos solo al entrenamiento.

| Estrategia | Accuracy prueba | Macro-F1 prueba | Aceptadas / prueba | Errores aceptados |
|---|---:|---:|---:|---:|
| baseline | 70.93 % | 0.8539 | 48/86 | 0 |
| discriminative | 65.12 % | 0.8313 | 47/86 | 0 |
| contrastive | 63.95 % | 0.8237 | 50/86 | 0 |

Ninguna alternativa mejora globalmente la referencia. El contrastivo acepta dos ejemplos más, pero pierde accuracy y macro-F1 generales. Por eso sigue experimental y no se activa automáticamente. La referencia compatible queda como estrategia predeterminada.

## Qué significan estos resultados

- Las 372 tomas históricas de LSM sin sesión registrada impiden certificar independencia entre personas. Los resultados son exploratorios, aunque las sesiones conocidas se mantienen agrupadas.
- No hay ejemplos de señas desconocidas etiquetadas como negativas. Cero errores aceptados en esta prueba de clases conocidas no significa cero falsos positivos en uso libre.
- La clase D tiene recuperación muy baja en validación en las tres variantes (0 % en referencia, 13,3 % en las otras). Esta observación la genera el análisis por clase; no existe ninguna regla para D en el código.
- La referencia llega a casi 100 % de aciertos de entrenamiento y aproximadamente 70 % de validación: memorizar los ejemplos disponibles no resuelve las diferencias entre sesiones.
- Los sondeos 3-NN aumentan macro-F1 de validación de 0,6735 (v4) a 0,6869 (v5), pero esa mejora de representación no se convirtió en una mejora neuronal general en este ensayo.
- Se requiere revisar las tomas sugeridas por semejanza con otras etiquetas y capturar las clases débiles en sesiones/personas nuevas. No se pueden confirmar etiquetas incorrectas sin revisar la seña que se pretendía grabar.

## Cambios y límites

La aplicación muestra pares/grupos confundidos, matriz por versión, métricas por clase, rechazos y comparaciones. El nuevo reparto persistente evita reutilizar reservas al ampliar vocabulario. Se conservan ejemplos de clases anteriores; la regresión se comprueba por clase. Las características nuevas, minería de ejemplos difíciles y preparación contrastiva están implementadas sin excepciones por letra/palabra.

Se conserva la BiLSTM compacta. No se aumentó su profundidad: la brecha de generalización y los ensayos no aportan evidencia de que una red mayor sea la solución. El rig y el modo local se conservan.

Pruebas: 94 ejecuciones Python y 6 archivos de pruebas JavaScript correctos. Incluyen captura, entrenamiento en datos temporales, igualdad del preprocesamiento de inferencia, estabilidad por modelo, serialización, rechazo, grupos reservados y compatibilidad. También se cargó y ejecutó el modelo activo antiguo (v2, seis clases) con los cambios instalados.

La latencia de cámara real y el reconocimiento de personas nuevas requieren una prueba presencial. La evaluación actual usa secuencias guardadas.

Archivos: `evaluacion-2026-10-28.json` contiene los resultados completos; `auditoria-2026-10-28.json`, los siete perfiles y los quince modelos anteriores.

Las tres versiones nuevas se guardan para consulta, sin modificar `current.json`. Para usar pesos nuevos es necesario entrenar/activar una versión y comprobarla con datos nuevos.
