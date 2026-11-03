# Usuarios y servidor compartido de Seña

> Guía de una configuración anterior. El modo local actual no exige iniciar sesión y solo ofrece el perfil LSM con salida en español; consulta README.md para el uso vigente.

En esta configuración anterior, cada servidor tenía un equipo que compartía ejemplos, etiquetas, modelos, métricas y actividad. El producto vigente está limitado a LSM con salida en español; los datos históricos de otros perfiles no se borran ni se cargan. No hay sincronización entre servidores diferentes.

## Comenzar en la computadora actual

```sh
cd /Users/apple/Documents/python_work/PdfManager/LSM
.venv/bin/python web_app.py --port 8765
```

1. Abre http://127.0.0.1:8765. Aparece la creación de la primera cuenta administradora.
2. Elige nombre, usuario y contraseña nueva (mínimo 12 caracteres). La primera
   cuenta será administradora. Este paso solo se permite en localhost, antes de
   configurar el acceso público. La contraseña administrativa anterior se conserva
   en la administración del vocabulario para confirmar los borrados.
3. En **Configuración → Cuentas y acceso**, crea una invitación. Su código es de un
   solo uso y vence en siete días. Compártelo por tu canal habitual; la aplicación
   no envía correos ni mensajes.
4. El integrante abre **Crear cuenta**, escribe el código y elige su contraseña.
5. Cada persona inicia sesión con su propia cuenta. Debe aceptar el procesamiento
   en ese servidor antes de activar la cámara.

Las tomas pendientes solo aparecen a su dueño y al administrador. Al nombrarlas
con **Guardar e integrar**, pasan al dataset compartido. Los otros usuarios ven
los nuevos conteos al actualizar o en el siguiente sondeo (aproximadamente 4 s).
Las sesiones y contraseñas se mantienen al reiniciar el servidor. Cerrar sesión
revoca el acceso y cierra las cámaras de esa cuenta. Caducidad: 12 h como máximo,
o 1 h sin peticiones. En la interfaz abierta el sondeo mantiene la sesión activa.
Desactivar una cuenta revoca sus sesiones; reactivarla permite volver a entrar
sin recuperar las sesiones antiguas. Sus ejemplos se conservan.

## Permisos

| Acción | Colaborador | Administrador |
|---|---|---|
| Reconocer, grabar, nombrar/descartar tomas propias | Sí | Sí |
| Ver vocabulario, ejemplos guardados, métricas y modelos | Sí | Sí |
| Revisar/exportar dataset por lengua | Sí | Sí |
| Gestionar pendientes de otro usuario o históricos sin dueño | No | Sí |
| Invitar, listar, desactivar/reactivar colaboradores | No | Sí |
| Importar, añadir abecedarios, entrenar y activar versiones | No | Sí |
| Borrar/reasignar ejemplos | No | Sí, con confirmación y contraseña administrativa existente |

No se crean perfiles de lengua por usuario; las contribuciones se reúnen dentro de
cada lengua. Los modelos no aprenden inmediatamente al guardar una toma: necesitan
un nuevo entrenamiento. El entrenamiento es único para el servidor y bloquea las
capturas mientras utiliza el dataset. Límite actual de cuatro cámaras abiertas,
una por cuenta; el procesamiento está serializado para proteger los archivos y
MediaPipe. Se ha preparado para un equipo pequeño, no se ha medido carga masiva.

El identificador de participante se fija en el servidor a `user:<UUID>`; no se puede
suplantar a otro participante mediante un campo del navegador. Los históricos
mantienen sus metadatos originales. Para evaluar entre personas hacen falta al
menos tres participantes con ejemplos de cada clase seleccionada.

## Alojarlo para acceder desde distintas casas

Esta actualización **no lo publica en Internet**. Hace falta un servidor persistente,
un dominio y HTTPS. Un enlace de localhost de otra computadora no sirve. La cámara
requiere HTTPS fuera de localhost ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)).

1. Usa una máquina con Python 3.11 y un entorno compatible con TensorFlow 2.15,
   MediaPipe 0.10.14 y NumPy 1.x, como el entorno existente. Instala las dependencias
   del proyecto. No se ha probado todavía la instalación en un servidor Linux nuevo.
2. Copia el código y, por un canal privado, `web_data/` y `models/` al mismo directorio.
   Conserva `web_data/admin/auth.json` (solo hash, nunca contraseña en claro).
   Si ya existen usuarios, copia también su SQLite. No uses un alojamiento que borre
   el disco al reiniciar ni ejecutes cada visita en un contenedor temporal.
3. Crea la primera cuenta administradora desde localhost antes de configurar
   `--public-url` (o conserva la base de cuentas al trasladar la instalación).
   Configura el dominio para ese servidor e instala un proxy HTTPS. Hay ejemplos
   en `deploy/Caddyfile.example` y `deploy/sena.service.example`; sustituye dominio,
   ruta y usuario de servicio por los reales.
4. Inicia **un único proceso** del backend detrás del proxy:

```sh
.venv/bin/python web_app.py --host 127.0.0.1 --port 8765 --public-url https://senas.ejemplo.com
```

5. Expón únicamente el proxy HTTPS a Internet. El proxy debe conservar el Host
   público. `--public-url` permite solo ese Host y origen, y activa cookies Secure.
   No se confía en cabeceras Forwarded enviadas por el cliente. No se permiten
   orígenes comodín ni acceso HTTP remoto sin configuración HTTPS.
6. Abre esa misma URL desde dos equipos e inicia sesión con cuentas distintas.
   Guarda una seña con el primero y comprueba el conteo compartido en el segundo.
   Comprueba captura, cierre de sesión y acceso administrativo. La validación de
   HTTPS, DNS y acceso desde casas distintas queda pendiente de disponer del servidor.

Caddy puede terminar HTTPS y reenviar al backend local
([documentación oficial](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)).
No ejecutes varios workers/réplicas: SQLite persiste cuentas, pero cámaras, bloqueos,
caché e inicio de entrenamientos pertenecen a un solo proceso.

## Datos y respaldo

- `web_data/accounts/team.sqlite3`: usuarios, hashes PBKDF2-SHA256 con sal individual,
  invitaciones y hashes de tokens de sesión. No se guarda la contraseña en claro.
- `web_data/datasets/`, `web_data/drafts/`, `web_data/vocabulary/`: datos compartidos
  y tomas pendientes con dueño. Los recibos de guardado también conservan el dueño.
- `models/` y `web_data/jobs/`: versiones, modelo activo y resultados compartidos.
- `web_data/admin/auth.json`: autorización administrativa existente.

Haz respaldo consistente con el servidor y entrenamiento detenidos: copia juntos
`web_data/` y `models/`. Al restaurarlos se recuperan cuentas, ejemplos y modelos.
Nunca publiques esas carpetas en un repositorio ni como archivos estáticos del sitio.
Los endpoints de datos exigen autenticación. Las cookies son HttpOnly y SameSite,
y cada sesión tiene su propio CSRF; con HTTPS también Secure. Estos controles siguen
las recomendaciones de [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

Las imágenes de la cámara se transmiten al servidor para procesarlas en memoria.
No se guardan archivos de video, audio ni fotografías. Se guardan los puntos de
referencia de las tomas completas, incluidas las pendientes, con acceso controlado.
Los ejemplos guardados y sus exportaciones están disponibles para los miembros.
Las imágenes y puntos no se envían a un servicio externo de IA.

No hay recuperación de contraseña por correo ni cambio de contraseña desde esta
versión. El equipo debe conservar sus credenciales y el respaldo del servidor.


## Verificación de esta actualización

- 68 pruebas Python y cinco suites JavaScript aprobadas.
- Pruebas con servidor HTTP real y cuentas aisladas: acceso no autenticado, CSRF
  cruzado, origen/Host, roles, invitación de un solo uso, guardado visible para
  otra cuenta, aislamiento de pendientes y cámaras, revocación y reconexión.
- Persistencia de cuentas/sesiones comprobada al abrir otra instancia del almacén.
- Interfaz: configuración inicial, invitación, login, rol colaborador y logout
  comprobados con pruebas de controlador; pantalla inicial instalada revisada
  en navegador sin errores de consola. No se creó una cuenta real de demostración.
- SHA256: 1604 archivos existentes de datasets, pendientes, vocabulario, modelos y
  configuración administrativa permanecieron iguales al instalar el código.
- Código anterior respaldado en `/private/tmp/sena-before-accounts`.
- No se probaron todavía un dominio público, TLS real ni acceso entre casas distintas.
  Los ejemplos de proxy/servicio requieren adaptarse al servidor que se contrate.
