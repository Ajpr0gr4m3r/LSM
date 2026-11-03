# Reconocimiento discriminativo de Seña

La aplicación activa actualmente solo el perfil LSM con salida en español. Los archivos NPZ y modelos históricos de otros perfiles se conservan en disco, pero no se cargan ni se ofrecen desde la interfaz. Los cambios de representación se identifican como `articulation-motion-v5`; solo los modelos nuevos usan esos canales. Los modelos antiguos siguen usando su preprocesamiento guardado.

## Problemas comprobados

- La comparación anterior exigía exactamente el mismo vocabulario. Al añadir una clase, dejaba de comprobar las clases conservadas.
- No había una reserva persistente entre entrenamientos. Cambiar la cantidad de ejemplos podía cambiar qué tomas se usaban para ajustar el modelo y cuáles se evaluaban.
- El modo local asignaba la misma identidad de participante a todos. Ahora permite escribir un código de participante, manteniendo la sesión de captura automáticamente.
- Los 30 canales geométricos anteriores describían extensión y separación de puntas, pero no cada articulación ni las velocidades explícitas.
- El ruido independiente de aumento podía cambiar demasiado la geometría de manos pequeñas. La estrategia nueva usa ruido pequeño, correlacionado en el tiempo y escalado por la palma.
- La inferencia usaba una constante global de estabilidad y una mala imagen podía actuar como fin de gesto aunque las manos siguieran presentes.

## Entrenamiento y captura

En **Entrenamiento → Estrategia** se puede elegir. La referencia queda como opción predeterminada: el ensayo actual no justifica hacer predeterminadas las alternativas experimentales.

- **Referencia anterior**: representación v4 y clasificación ponderada por clase.
- **Articulaciones y ejemplos difíciles**: representación v5 y ponderación actualizada con las dificultades de entrenamiento. El peso relativo de un ejemplo está acotado; cada clase conserva la misma suma de pesos.
- **Contrastivo**: añade una preparación supervisada del encoder usando dos ejemplos por clase antes de clasificar. Es experimental, no garantiza superar las otras opciones.

Al seleccionar nuevas señas se incluyen también las clases del modelo activo que aún tienen grabaciones. Si una clase conservada no tiene suficientes ejemplos, el entrenamiento informa el problema. No se inventan ejemplos ni se sustituyen etiquetas. Los duplicados exactos de la misma clase se cuentan una vez; los duplicados con etiquetas distintas bloquean el entrenamiento.

Usa el mismo código de participante al volver a grabar. Cuando cada clase tiene suficientes personas registradas, la separación usa personas; de lo contrario usa sesiones completas y lo indica. Los ejemplos históricos sin sesión permiten solo una evaluación exploratoria. No se atribuyen retrospectivamente personas a esas tomas.

`models/<lengua>/evaluation_split.json` reserva los grupos y huellas de cada conjunto. Ampliar el vocabulario conserva las reservas. Si una nueva agrupación de personas uniría entrenamiento y prueba históricos, se detiene con una explicación. No borres esa reserva para buscar una puntuación más alta.

## Representación y decisiones

Los 86 canales adicionales conservan los anteriores y añaden ángulos de flexión, distancias a la palma, ejes y normal de la mano, velocidades de muñeca y puntas, separación de manos y posición facial respecto al torso. Las relaciones entre manos/cuerpo usan XY: la profundidad de MediaPipe tiene orígenes distintos para cada mano. No se reflejan manos para aumentar datos ni se elimina su orientación. Captura e inferencia usan la imagen en espejo y la misma función `prepare_sequence`.

La arquitectura temporal compacta BiLSTM se conserva. El entrenamiento contrastivo solo modifica cómo aprende el encoder; los archivos de inferencia siguen conteniendo capas Keras estándar y se cargan con `safe_mode=True`.

La validación calibra temperatura, confianza y diferencia entre las dos primeras clases. Una clase sin evidencia suficiente se rechaza. Los filtros de forma y movimiento usan referencias de entrenamiento, limitadas a 64 por clase en entrenamientos nuevos. La inferencia mantiene estabilidad temporal, limpia secuencias interrumpidas y evita duplicar un gesto hasta que se retiren las manos. El video en vivo aún requiere una prueba con personas para medir su latencia completa y los límites temporales reales; los ensayos sobre secuencias aisladas no sustituyen esa prueba.

## Evaluación y recuperación

**Entrenamiento → Versiones → Comparar y ver curvas** muestra curvas, matriz, precision/recall/F1 por clase, errores aceptados, rechazos, pares en ambas direcciones y grupos confundidos. **Descargar evaluación** exporta el informe JSON. Los modelos históricos con matriz también muestran sus pares automáticamente.

El diagnóstico compara representaciones con un clasificador 3-NN fijo, señala la brecha entre entrenamiento y validación, problemas de calidad y ejemplos cuya geometría se parece a otra etiqueta. Son indicios para revisión, no una identificación infalible de la causa ni un cambio automático de etiquetas. La arquitectura debe juzgarse mediante ensayos comparables; más capas no garantizan mejor precisión.

La selección de checkpoint usa macro-F1 y la peor recuperación por clase. La comparación entre versiones comprueba las clases comunes por separado; una subida del promedio no oculta un retroceso de recall. La comparación de prueba excluye entrenamiento y calibración de ambas versiones y se informa por separado de la selección. Si falta procedencia independiente, la comparación se marca como no certificable. Una versión con datos históricos sin sesión o evidencia insuficiente se guarda sin reemplazar automáticamente el modelo activo.

No existe un conjunto de señas desconocidas reales en los datos actuales. Su tasa de falsos positivos se informa como **no evaluada**. Los errores aceptados entre clases conocidas sí se cuentan. Tampoco se afirma generalización a personas nunca vistas a partir de tomas sin procedencia.

Las versiones anteriores pueden recuperarse con el control existente de restauración, que comprueba vocabulario, dimensiones y contraseña administrativa.

## Ejecución

```sh
.venv/bin/python web_app.py
```

Abre `http://127.0.0.1:8765`. Las nuevas características, aprendizaje discriminativo y calibración requieren volver a entrenar. Reiniciar la página por sí solo no cambia los pesos del modelo existente.

Ensayo desde terminal, sin activar el resultado:

```sh
.venv/bin/python web_train.py --language lsm --epochs 40 --job-id IDENTIFICADOR_HEXADECIMAL_DE_32_CARACTERES --strategy contrastive --no-activate
```

## Fuentes técnicas

- [Khosla et al., Supervised Contrastive Learning](https://arxiv.org/abs/2004.11362).
- [Scikit-learn: validación por grupos](https://scikit-learn.org/stable/modules/cross_validation.html).

Los resultados del artículo contrastivo no se transfieren a Seña. La decisión debe basarse en los ensayos del proyecto.
