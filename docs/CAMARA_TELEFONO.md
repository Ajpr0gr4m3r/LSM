# Cámara del teléfono y conversación

Seña permite conversar entre una computadora y un teléfono. La persona del teléfono puede hacer señas frente a la cámara o escribir; la persona de la computadora puede responder por texto. Los mensajes aparecen en ambas pantallas y se leen en voz alta si el navegador dispone de una voz compatible.

El teléfono envía fotogramas a la Mac para ejecutar el modelo de la lengua elegida al crear la sala. Solo se reconocen las señas aprendidas por ese modelo. Los siete perfiles mantienen sus datos y modelos separados.

## 1. Conectar el teléfono a Tailscale

1. Instala Tailscale desde App Store o Google Play.
2. Inicia sesión con la misma cuenta que utilizas en la Mac, o con una cuenta invitada a su misma red Tailscale.
3. Acepta la configuración VPN cuando el sistema la solicite y activa Tailscale.
4. Comprueba que la Mac y el teléfono aparezcan conectados a la misma red privada.

Tailscale debe permanecer conectado en ambos dispositivos. La Mac debe estar encendida y Seña debe continuar ejecutándose durante la conversación.

## 2. Revisar el acceso HTTPS privado

En la Mac, ejecuta:

```sh
tailscale serve status
```

Para esta instalación, la configuración de Seña es:

```text
https://macbook-air-de-xionel.tailbc2ab0.ts.net (tailnet only)
|-- / proxy http://127.0.0.1:8765
```

Si ya aparece esa configuración, continúa con el siguiente paso. Si aparece `No serve config`, configúrala con:

```sh
tailscale serve --bg --https=443 --yes http://127.0.0.1:8765
```

Si aparece otro servicio, conserva su configuración y revisa cómo alojar Seña antes de reemplazarlo. Utiliza Serve para este acceso privado.

Los navegadores móviles requieren HTTPS para acceder a la cámara. `http://127.0.0.1:8765` abre Seña en la Mac; en el teléfono esa dirección apunta al propio teléfono.

## 3. Iniciar Seña en la Mac

Si Seña todavía no está ejecutándose:

```sh
cd "/Users/apple/Documents/python_work/lia projects/LSM"
.venv/bin/python web_app.py --phone-origin https://macbook-air-de-xionel.tailbc2ab0.ts.net
```

Mantén abierta la terminal del servidor y entra desde la Mac a:

<http://127.0.0.1:8765/>

La dirección `.ts.net` anterior corresponde a esta Mac. Si utilizas otro servidor o cambia su nombre, sustituye el valor de `--phone-origin` por la dirección HTTPS indicada por `tailscale serve status`.

`--phone-origin` conserva la aplicación principal en modo local. A través de HTTPS permite abrir la página móvil mediante su enlace temporal; no publica el inicio, dataset, cuentas ni administración. Abre la sala desde el QR o su enlace completo, no desde la raíz de la dirección `.ts.net`.

### Si aparece “Address already in use”

El puerto `8765` ya está ocupado. Antes de intentar iniciar otra instancia, abre <http://127.0.0.1:8765/>: si responde Seña, utiliza esa instancia y recarga la página.

Para identificar el proceso que ocupa el puerto:

```sh
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

Si necesitas reiniciar Seña, detén su instancia desde la terminal donde se ejecuta con `Ctrl+C` y vuelve a utilizar el comando de inicio. No detengas un proceso sin comprobar a qué aplicación pertenece. Reiniciar el servidor elimina las salas temporales; después debes crear una sala y un QR nuevos.

## 4. Crear la sala y abrir la cámara

1. En la Mac, selecciona la lengua de señas que van a usar.
2. Entra en **Conversación**. También puedes pulsar **¿No tienes cámara? Usar teléfono** desde Reconocimiento.
3. Acepta compartir los mensajes y señas en la sala temporal y pulsa **Crear conversación**.
4. Escanea el QR con el teléfono o copia su enlace completo y ábrelo en Safari o Chrome.
5. En la página móvil, acepta el envío de fotogramas y pulsa **Activar cámara**.
6. Permite el acceso a la cámara cuando el navegador lo solicite.

El reconocimiento necesita un modelo entrenado para el perfil seleccionado. El chat escrito funciona aunque la cámara esté apagada.

## 5. Escribir mediante señas y responder

Las señas confirmadas se acumulan en un borrador visible:

- Las letras consecutivas se unen: `H` + `O` + `L` + `A` → `HOLA`.
- Las palabras reconocidas se separan con espacios.
- Cada nueva seña confirmada reinicia la espera.
- Después de **4 segundos sin una nueva confirmación**, el mensaje se envía automáticamente a la otra pantalla.

Mantener una misma seña confirmada no genera mensajes repetidos. Para repetir la misma letra, baja las manos unos instantes y vuelve a hacerla. Las coincidencias provisionales o rechazadas no se añaden al borrador. El sistema reúne etiquetas reconocidas; no aplica traducción gramatical de conversaciones libres.

En cualquiera de las pantallas puedes escribir una respuesta y pulsar **Enviar**. La otra pantalla mostrará el mensaje y podrá leerlo con la voz disponible del navegador.

## 6. Terminar y privacidad

La sala vence una hora después de crearla. **Terminar conversación**, en la Mac, elimina la sala y revoca el enlace. **Desconectar teléfono** apaga su cámara; la sala puede seguir utilizándose por texto hasta que termine o venza.

Las salas, borradores y mensajes se mantienen en memoria, sin guardarse en archivos ni integrarse al dataset. Seña no conserva video ni audio de la conversación. El enlace del QR da acceso a los mensajes de esa sala: compártelo únicamente con la otra persona.

## Problemas frecuentes

### No se puede activar la cámara

- Comprueba que Tailscale esté conectado en ambos dispositivos.
- Abre el enlace completo del QR por HTTPS en Safari o Chrome.
- Marca el consentimiento de cámara y permite el acceso en el navegador.
- Si lo rechazaste, revisa los permisos de cámara de esa página en la configuración del navegador.
- Comprueba que el perfil elegido tenga un modelo entrenado.

### Los botones no responden o los mensajes no se envían

Recarga ambas páginas para cargar los scripts actuales. El chat debe estar disponible sin activar la cámara. Si la sala venció o reiniciaste el servidor, crea otra y escanea su nuevo QR. Revisa el mensaje de error que aparece al final de la página móvil.

Si el enlace no abre, verifica también `tailscale serve status` y que Seña responda en la Mac. El QR se genera a partir de `--phone-origin`; su presencia no garantiza por sí sola que Tailscale o el proxy estén conectados.

### No se escucha la voz

Revisa el volumen y las voces instaladas del teléfono o la computadora. La reproducción depende del navegador; los mensajes escritos siguen disponibles aunque la voz falle.
