# Señas con movimiento: evaluación del 31 de octubre de 2026

El filtro temporal nuevo conserva 16 posiciones ordenadas de muñeca y las cinco puntas de cada mano. Compara desplazamiento, velocidad con signo y longitud de recorrido, conserva lateralidad y dirección y enmascara ausencias. La normalización es idéntica durante ajuste e inferencia. Los modelos anteriores conservan su descriptor por versión.

El entrenamiento detecta clases con movimiento a partir de la distribución de recorridos. En los datos actuales identificó J sin usar nombres de letras en las reglas. La tolerancia absoluta anterior era demasiado amplia: podía aceptar un recorrido quieto. Ahora se calibra una comparación contra clases con distinto comportamiento de movimiento, usando entrenamiento y validación. Cuando esa comparación aporta evidencia para una clase móvil, se evita duplicar el veto con una comparación estática de forma. Permanecen los controles de forma absoluta, confianza, ambigüedad y estabilidad.

## Ensayo con los pesos del modelo activo

Fuente: `23dd977294bd4d439cba27d6fc15a534`. Versión corregida: `00000000000000000000000000000034`. No se aprendieron clases nuevas ni se modificaron los pesos. Se usaron los mismos 643 ejemplos de entrenamiento, 186 de validación y 273 de prueba. Los parámetros se ajustaron con validación; las decisiones de este ensayo no seleccionan pesos nuevos.

| Resultado en prueba histórica | Antes | Después |
|---|---:|---:|
| J: correctas confirmadas / 61 | 29 | 44 |
| I: correctas confirmadas / 16 | 15 | 15 |
| Total: correctas confirmadas / 273 | 184 | 199 |
| Errores aceptados | 27 | 22 |
| Total de confirmaciones | 211 | 221 |

B pierde un acierto (8 a 7 de 27); H gana uno (34 a 35 de 40). El resto conserva su recuperación confirmada. La comparación por clase pasa la tolerancia existente de cinco puntos porcentuales, tanto en validación como en prueba. Esto no demuestra que todas las clases mejoren.

La reserva es histórica y ya fue consultada en trabajos anteriores. La calibración comparte validación por falta de sesiones separables. Estos resultados son exploratorios sobre secuencias completas, no una medición nueva de cámara en vivo ni de personas desconocidas. Tampoco hay una prueba de falsos positivos de señas desconocidas reales.

## Alternativas descartadas y entrenamiento

Una espera obligatoria hasta detener totalmente la mano rechazó demasiadas secuencias de J y no se instaló. También se ejecutó un entrenamiento aislado de 12 épocas con trayectorias/velocidades y variación temporal. Su macro-F1 de prueba fue aproximadamente 0.728 frente a 0.773 del modelo de origen; por ello sus pesos no se activaron. Sus resultados completos están en el JSON adjunto.

La opción **Entrenamiento → Estrategia → Trayectoria y velocidad · experimental** permite probar nuevos entrenamientos. Usa la representación de articulaciones y velocidad v5 y el filtro de trayectorias v2. Cambia moderadamente la velocidad, siempre en el mismo orden, y añade una breve permanencia final sin aumentar la cantidad de variantes frente al aumento anterior. El mejor checkpoint conserva la selección por métricas balanceadas, los grupos reservados y todas las clases anteriores con ejemplos.

Para grabar una seña móvil, parte de su posición inicial, realiza el recorrido completo una vez y conserva brevemente la posición final. Graba las señas quietas sin añadir ese recorrido. Una postura inicial compartida no permite anticipar qué movimiento hará después la persona: el sistema necesita observarlo. La confirmación desde 90 % sigue sujeta a estos filtros.

## Pruebas y recuperación

Se comprobaron forma idéntica con trayectoria distinta, orden inverso, mano ausente, normalización por escala/posición, aumento temporal, rechazo de una postura quieta pese a 99 % de confianza, compatibilidad de filtros anteriores, continuidad y duplicados. Trece pruebas de movimiento/decisiones y una prueba de entrenamiento/guardado/carga pasaron, además de los checks JavaScript de la página, voz y diagnóstico.

La versión original se conserva en Entrenamiento → Versiones y puede restaurarse con el control administrativo. No se alteraron los datasets ni las particiones históricas.
