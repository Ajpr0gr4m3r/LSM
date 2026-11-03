# Validación de Seña Estudio

- 57 pruebas Python superadas: captura, calidad, persistencia, compatibilidad,
  entrenamiento sintético temporal, inferencia, administración, agrupación,
  restauración de versiones e intercambio ZIP.
- Pruebas Node superadas: tandas consecutivas, selección/desconexión de cámara y
  contrato de las cinco vistas (sin IDs duplicados ni rig en la página).
- Revisión en navegador: modos claro y oscuro; navegación y controles reales;
  ancho móvil de 390 px con scrollWidth=clientWidth=390; viewport restaurado al terminar.
- Auditoría por HTTP local con datos reales: LSM, 372 tomas válidas, 0 duplicadas
  exactas, 3 avisos de encuadre. Ningún ejemplo fue eliminado por esta auditoría.
- Las 372 tomas LSM revisadas no contenían procedencia histórica. Esto se muestra
  como limitación y no se interpreta como evaluación entre personas independientes.
- Verificadas 12 versiones existentes y exportación ZIP en memoria de 372 tomas.
- Carga e inferencia finita comprobadas con el modelo activo existente
  `6f91a4f122644d4bb6a3144893b573f3`, preprocesamiento `body-hand-relative-v2`,
  salidas A, B, C, E, F, G. No se volvió a entrenar ni se modificaron sus pesos.
- El despliegue comprobó por SHA256 que 515 archivos de datasets, vocabularios,
  modelos y credenciales seleccionados permanecieron idénticos. Copia del código
  previo en `/private/tmp/sena-pre-studio-backup`.

Las mejoras nuevas de preprocesamiento y guardia temporal requieren reentrenar.
Las pruebas no demuestran un aumento porcentual de precisión real ni rechazo
perfecto de gestos desconocidos. Se necesita una evaluación nueva con personas,
sesiones, cámaras y negativos independientes para medirlo.
