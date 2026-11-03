# Acceso privado del laboratorio desde casa

La opción preparada usa **Tailscale Serve** y la cuenta individual de cada persona
en Seña. Los datos permanecen en esta Mac: todos entran al mismo servidor y los
modelos/ejemplos guardados son compartidos, con las siete lenguas separadas.

## Activación que requiere al propietario

1. Completa la instalación oficial de Tailscale, revisa sus términos y autoriza su
   extensión/VPN cuando macOS lo solicite. El instalador descargado se verificó por
   SHA256 y firma/notarización de Tailscale Inc.; no contiene ejemplos del proyecto.
2. Abre Tailscale e inicia sesión en la cuenta/red que usarán en el laboratorio.
   El propietario debe elegir y aceptar personalmente cualquier acuerdo o plan.
   No se ha contratado ningún servicio ni se ha elegido un plan de pago.
3. En la carpeta `deploy`, ejecuta **Activar-acceso-privado.command**. Si Tailscale
   solicita habilitar HTTPS, completa la autorización y ejecuta el archivo otra vez.
4. El comando obtiene el nombre real de esta Mac y muestra una URL HTTPS. No hay
   una dirección remota válida antes de completar Tailscale. El backend reinicia
   sobre los mismos datos y se aceptan únicamente el Host/origen HTTPS configurados.
5. Invita a los integrantes a la red de Tailscale que elegiste y dales acceso solo
   a esta Mac/puerto 443 con las reglas de acceso de tu laboratorio. Deben instalar
   Tailscale e iniciar sesión en sus computadoras. No se envían invitaciones desde
   Seña automáticamente ni se han añadido personas sin indicar sus cuentas.
6. Además, desde **Configuración → Cuentas y acceso** de Seña, crea un código por
   integrante. Cada código sirve para una cuenta y vence en siete días.
7. Prueba con otro equipo: abre la URL HTTPS, crea/inicia sesión en Seña, graba y
   guarda una toma. Comprueba desde tu cuenta que aumentó el conteo de esa lengua.
   Verifica que otra cuenta no pueda usar tus pendientes y que solo el administrador
   pueda borrar. Esta prueba entre casas requiere las cuentas/red conectadas.

El acceso a la red Tailscale y la cuenta en Seña son dos controles diferentes.
No se usa Tailscale Funnel ni se publica el sitio anónimamente. El helper rechaza
Funnel activo o una configuración de Serve ajena en lugar de sobrescribirla.
Las imágenes se procesan en memoria en la Mac del servidor, no en una API externa
 de IA; se guardan puntos de las tomas, no videos ni audio.

## Servicio persistente en macOS

```sh
.venv/bin/python private_server.py install-service
```

El servicio `mx.sena.laboratorio` inicia un único supervisor al entrar en esta
cuenta de macOS. El supervisor inicia `web_app.py` y lo recupera si termina;
los cambios de URL reinician solamente su propio proceso. No inicia otra copia
si otro supervisor tiene el bloqueo. Detén la instancia manual anterior antes
de instalar el servicio por primera vez.

- Configuración: `web_data/server/private.json`.
- Registros: `web_data/server/service.log` y `service-error.log`.
- Estado: ejecuta `deploy/Estado-acceso-privado.command`.
- Volver a localhost: ejecuta `deploy/Volver-a-local.command` mientras Tailscale
  siga conectado. Desactiva solo el proxy de Seña y conserva datos/cuentas.
- Reiniciar el servicio: `launchctl kickstart -k gui/$(id -u)/mx.sena.laboratorio`.
- Detenerlo: `launchctl bootout gui/$(id -u)/mx.sena.laboratorio`.

La Mac debe permanecer encendida, despierta, conectada y con esta sesión de macOS
iniciada. Cerrar la tapa, dormir o apagar la Mac interrumpe el acceso. No se cambiaron
las preferencias de energía. Para disponibilidad continua conviene trasladar el
mismo servidor a una máquina del laboratorio que permanezca encendida. Se
mantiene el límite actual de cuatro cámaras simultáneas, una por cuenta.

Tailscale puede requerir un plan según el tipo y tamaño de organización; no se
promete acceso gratuito ilimitado para un laboratorio. Revisa el plan antes de
aceptarlo. Los datos del proyecto no se han subido a un alojamiento externo.

Documentación oficial:
[Serve privado](https://tailscale.com/docs/use-cases/application-testing/share-local-dev-server-with-team),
[CLI Serve](https://tailscale.com/docs/reference/tailscale-cli/serve),
[instalación macOS](https://tailscale.com/docs/concepts/macos-variants),
[planes educativos](https://tailscale.com/docs/account/manage-plans/free-plans-discounts).


## Estado comprobado de esta instalación

Actualizado el 28 de octubre de 2026: con la Mac desbloqueada se activó el
LaunchAgent `mx.sena.laboratorio` y el instalador del servicio comprobó una
respuesta HTTP correcta de Seña. La instancia temporal fue cerrada antes de
iniciar el servicio automático para evitar dos procesos usando los mismos datos.

Tailscale está instalado y conectado. El propietario habilitó Serve/HTTPS y
el acceso privado está activo. Se comprobó desde esta Mac que la URL HTTPS
abre Seña con certificado válido, que los datos requieren iniciar sesión y que
las cookies usan Secure, HttpOnly y SameSite=Strict. Serve no tiene Funnel activo.
El comando de estado muestra la URL real y verifica el acceso HTTPS.

Falta la prueba desde un segundo equipo del laboratorio: conectarlo a la misma
red Tailscale, entrar con una cuenta de Seña y guardar una toma compartida.
No se han enviado invitaciones a integrantes. El acceso depende de que esta Mac
permanezca encendida, despierta, conectada y con la sesión de macOS iniciada.
