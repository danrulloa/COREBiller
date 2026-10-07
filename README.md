# COREBiller

COREBiller ayuda a un Core Facility a organizar su catálogo de servicios, clientes, cotizaciones y seguimiento de servicios realizados. Se ejecuta en un solo computador y guarda allí los datos. No necesitas una cuenta, contraseña ni conexión a internet para usarlo después de descargarlo.

Esta guía está escrita para personas usuarias, no para desarrolladores. No necesitas saber qué es Git: puedes descargar el proyecto como un archivo ZIP desde GitHub.

## Antes de empezar

- Un computador con Windows o macOS.
- Python 3.10 o posterior. En Windows, el lanzador intenta encontrar Python por ti. En Mac, necesitas tenerlo instalado.
- Excel o Google Sheets para preparar el catálogo, si quieres importar tus servicios desde una hoja.

COREBiller es un MVP para pruebas piloto. **No se ha validado como reemplazo completo del Excel ni de todos los procesos de MicroCore.** EjemploCORE incluye información inventada para mostrar el recorrido; no tiene validez comercial. Los Core que crees comienzan vacíos.

## 1. Descargar COREBiller desde GitHub

Haz esto una sola vez para instalarlo. Para usar COREBiller en los días siguientes, ve directamente a «Abrir COREBiller cada vez que lo uses».

1. Abre el repositorio: [github.com/danrulloa/COREBiller](https://github.com/danrulloa/COREBiller).
2. En la página del proyecto, pulsa el botón verde **Code** y luego **Download ZIP**.
3. Cuando termine la descarga, busca el archivo ZIP en la carpeta **Descargas** y descomprímelo. En Windows, haz clic derecho y elige **Extraer todo**. En Mac, haz doble clic.
4. Mueve la carpeta resultante a un lugar fácil de encontrar, por ejemplo **Documentos**. No ejecutes el programa dentro del archivo ZIP.

No tienes que instalar Git ni copiar comandos de Git para usar la aplicación.

## 2. Abrir COREBiller por primera vez

La aplicación se inicia desde una ventana de terminal. La terminal es una ventana donde se escribe una instrucción corta para abrir el programa; no necesitas programar.

### En Windows

1. Abre el **Explorador de archivos** y entra a la carpeta descomprimida `COREBiller-main`.
2. Haz clic derecho en un espacio vacío dentro de esa carpeta y elige **Abrir en Terminal**. En algunas versiones de Windows aparece **Abrir ventana de PowerShell aquí**.
3. Escribe esta línea y pulsa **Enter**:

   ```powershell
   .\Start-COREBiller.ps1
   ```

4. Deja abierta la ventana de Terminal. Cuando aparezca una dirección que comienza por `http://127.0.0.1:8765`, abre esa dirección en Chrome, Edge o Firefox.

Si Windows informa que no permite ejecutar el archivo, en esa misma ventana prueba:

```powershell
powershell -ExecutionPolicy Bypass -File .\Start-COREBiller.ps1
```

### En Mac

1. Abre **Terminal**. Puedes encontrarla con Spotlight: pulsa `Command + Espacio`, escribe `Terminal` y pulsa `Enter`.
2. Comprueba que tengas Python 3.10 o posterior: escribe `python3 --version` y pulsa **Enter**. Si no aparece una versión o es anterior a 3.10, instala Python desde [python.org/downloads](https://www.python.org/downloads/macos/).
3. En Terminal, escribe `cd ` (incluye un espacio al final, pero todavía no pulses Enter).
4. Desde Finder, arrastra la carpeta descomprimida `COREBiller-main` a la ventana de Terminal. Pulsa **Enter**.
5. Escribe `python3 app.py` y pulsa **Enter**.
6. Deja abierta Terminal. Cuando aparezca `http://127.0.0.1:8765`, abre esa dirección en Safari, Chrome o Firefox.

COREBiller no necesita instalar paquetes adicionales.

### Crear tu Core

Al abrir la página por primera vez, elige **Crear mi Core**, escribe el nombre del Core y continúa. Eso crea un espacio vacío para ese Core. También puedes abrir **EjemploCORE** para probar la aplicación con información ficticia.

COREBiller no comprueba quién eres: el nombre y el rol que eliges son locales y autodeclarados. Por eso esta versión es solo para uso en el computador donde se inicia; no la publiques como portal ni la compartas en una red.

## 3. Preparar el catálogo de servicios

Cada Core tiene su propio catálogo. Puedes registrar los servicios uno por uno en **Servicios y tarifas**, o importar varios desde la plantilla CSV.

1. En COREBiller, selecciona el Core que quieres configurar y el rol **Admin**.
2. Abre **Servicios y tarifas** y pulsa **Importar CSV**.
3. Pulsa **Descargar plantilla CSV**. El archivo se descargará en la carpeta de descargas de tu navegador.
4. Abre el CSV con Excel o impórtalo en Google Sheets. Conserva la primera fila, que contiene los títulos de las columnas.
5. Agrega una fila por cada servicio y tarifa. Llena todas las columnas:

   - `code`: código único, por ejemplo `MET-001`.
   - `name`: nombre claro del servicio. Si hay variantes, aclara el año, modalidad o alcance en el nombre.
   - `unit`: unidad que se cotiza, por ejemplo `muestra`, `hora` o `corrida`.
   - `category`: clasificación o tipo de tarifa, por ejemplo `Tarifa 2026`.
   - `price`: precio en pesos colombianos como número, por ejemplo `125000`. No escribas `$`, `COP` ni puntos para separar miles.

6. Guarda o descarga el archivo como **CSV UTF-8**. En Excel, usa **Guardar como** y elige **CSV UTF-8 (delimitado por comas)**. En Google Sheets, elige **Archivo → Descargar → Valores separados por comas (.csv)**.
7. Vuelve a COREBiller, selecciona ese archivo y pulsa **Validar e importar**.
8. Comprueba que los servicios y los precios aparezcan correctamente antes de crear cotizaciones.

Si la aplicación encuentra datos incorrectos o nombres duplicados, no importa una parte del catálogo: informa el error para que puedas corregir el archivo y volverlo a intentar. Si importas un código que ya existe, se actualiza ese servicio. Un servicio que ya no esté en el archivo no se elimina. Las cotizaciones anteriores conservan los precios con los que fueron emitidas.

La [guía detallada del catálogo y archivos en la nube](docs/configurar-catalogo.md) explica las columnas y reglas con más detalle.

### Usar un archivo guardado en la nube

Puedes guardar el CSV en una carpeta de OneDrive o Google Drive que esté sincronizada con este computador. Cuando cambies precios, selecciona e importa otra vez el CSV desde COREBiller.

COREBiller no queda conectado automáticamente a un enlace de Excel Online o Google Sheets: cambiar la hoja en internet no actualiza la aplicación. La base de datos de COREBiller se guarda localmente en este computador.

## 4. Configurar el Core y empezar a trabajar

Un recorrido habitual es:

1. En **Administración**, configura el nombre, los datos de contacto, las condiciones comerciales y el logo PNG del Core.
2. En **Servicios y tarifas**, revisa o completa los servicios y sus precios.
3. En **Clientes**, registra las personas e instituciones que aparecerán en las cotizaciones.
4. Crea una cotización, revísala y emítela. Desde su vista puedes imprimirla o guardarla como PDF.
5. Registra la aceptación y usa **Seguimiento de servicios** para anotar los servicios ejecutados, pagos y documentos relacionados.
6. Usa los informes para revisar la actividad y exportar CSV.

Los cambios de precio se hacen manualmente. Cambiar el catálogo no modifica cotizaciones anteriores. COREBiller guarda datos, pero no envía correos, pagos, facturas ni trámites institucionales por ti.

## 5. Abrir COREBiller cada vez que lo uses

Después de descargar y configurar COREBiller, no tienes que volver a descargar el proyecto para el uso diario:

1. Abre la carpeta `COREBiller-main` que guardaste en tu computador.
2. Abre una ventana de Terminal dentro de esa carpeta, usando los pasos de Windows o Mac descritos arriba.
3. En Windows, ejecuta `.\Start-COREBiller.ps1` y pulsa **Enter**. En Mac, ejecuta `python3 app.py` y pulsa **Enter**.
4. Abre `http://127.0.0.1:8765` en el navegador.
5. Selecciona el Core y el rol que vas a usar.
6. Al terminar, vuelve a la ventana de Terminal y pulsa `Ctrl + C`. Puedes cerrar la ventana después.

**Deja abierta la ventana de Terminal mientras uses COREBiller.** Si la cierras, la aplicación se detiene. La próxima vez que la inicies, tus datos seguirán allí: se guardan en la carpeta `data` del proyecto. No borres esa carpeta. Para hacer una copia de seguridad, usa la opción de respaldo en Administración.

Si ves un mensaje de que el puerto está ocupado, probablemente COREBiller ya está abierto en otra ventana. Vuelve a esa ventana y usa la dirección que muestra; no abras una segunda instancia.

## Privacidad y límites

Los datos se guardan en bases locales, una por Core, dentro de `data/`. No subas esa carpeta a GitHub ni la pongas en una carpeta sincronizada para usar simultáneamente desde varios computadores. Una hoja CSV en OneDrive o Google Drive puede servir para preparar el catálogo, pero la base de COREBiller no es compartida ni sincronizada entre equipos.

COREBiller todavía no incluye inicio de sesión con cuenta institucional, autenticación Microsoft/Google, trabajo simultáneo en varios equipos, firma digital, portal público ni conexión automática con Excel Online o Google Sheets. Revisa [los casos de MicroCore y su cobertura](docs/casos-microcore.md) antes de usar el MVP como sustituto de procesos existentes.

## Información para quien mantiene el proyecto (opcional)

COREBiller usa Python 3.10 o posterior y la biblioteca estándar; no necesita paquetes externos para arrancar. Para ejecutar las pruebas operativas:

```powershell
python -m unittest discover -s tests -v
```

La prueba que necesita el libro privado `MicroAccounts.xlsx` se omite si el archivo no está presente. Ese libro y las bases de datos no están incluidos en GitHub. No publiques datos reales ni resultados privados.
