# Validación y reconocimiento al ampliar vocabulario

Cambios: calibración conjunta por clase de confianza, margen, forma, rival y movimiento. La forma absoluta se conserva; el veto contra señas similares se mantiene cuando aporta evidencia. Los empates no endurecen la confianza sin justificación. La decisión nueva usa exactamente la misma ventana en evaluación e inferencia; la estabilidad temporal se mantiene sin mezclar votos de gestos anteriores. Modelos históricos conservan su comportamiento.

Selección de épocas y calibración se separan por grupos completos y persistentes cuando hay al menos tres tomas y dos grupos por clase en cada parte. Si no alcanza, se declara validación compartida y no se activa automáticamente. Los intervalos de incertidumbre distinguen secuencias y sesiones; no cuentan fotogramas como observaciones independientes. Las clases previas con grabaciones se conservan incluso si el modelo había sido invalidado tras borrar otra clase.

La interfaz de versiones muestra cobertura, errores aceptados y aciertos descartados por etapa. Una clase sin evidencia suficiente sigue rechazada con explicación específica.

## Ensayo exploratorio con pesos existentes

Origen: `8c8c371cd23848cba5f55e996d71efd7`, ocho clases. La política se ajustó con las 105 secuencias de validación, sin usar las 86 de prueba para ajustar parámetros.

| Conjunto | Aceptadas antes | Aceptadas después | Errores aceptados antes/después |
|---|---:|---:|---:|
| Validación (105) | 68 | 72 | 0 / 0 |
| Prueba histórica (86) | 49 | 57 | 0 / 0 |

Son resultados de secuencias guardadas, no de cámara en vivo. La prueba histórica ya se había consultado en trabajos anteriores; no demuestra generalización nueva. No hay un conjunto de señas desconocidas para medir sus falsos positivos. No se entrenaron pesos nuevos ni se aprendieron clases adicionales.

Versión recalibrada guardada sin activar: `80bf76e56ce2432ca103302dc8386eee`. Se puede comparar y restaurar desde Entrenamiento → Versiones con el control administrativo existente. El modelo activo se conserva.

Para las nuevas clases, hacen falta grupos completos representados en entrenamiento, validación y prueba. Muchas tomas de una misma sesión no sustituyen sesiones independientes. Los dos últimos entrenamientos fallaron por esa falta de procedencia separable; no se ha borrado la reserva histórica para inflar métricas.

## Uso

Desde la carpeta actual del proyecto: `.venv/bin/python web_app.py`. Abre http://127.0.0.1:8765. Los próximos entrenamientos usarán la nueva calibración y el protocolo de validación automáticamente. Reentrena con las clases nuevas y sesiones variadas para aprenderlas; reiniciar el servidor no añade clases al modelo.

Pruebas: 108 pruebas Python de la suite completa, más una prueba adicional de transición de gestos (6/6 en el módulo de decisiones); 8 archivos de pruebas JavaScript, incluido análisis sintáctico completo.

Referencias: [calibración](https://scikit-learn.org/stable/modules/calibration.html) y [validación por grupos](https://scikit-learn.org/stable/modules/cross_validation.html). La calibración se evalúa separadamente de su ajuste; los grupos relacionados no se reparten entre conjuntos.
