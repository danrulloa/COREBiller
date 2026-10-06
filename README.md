# COREBiller local · MVP v3

Herramienta genérica para Core Facilities. Catálogo, clientes, cotizaciones, registro de servicios ejecutados, pagos, correcciones e informes; base SQLite independiente por Core. Funciona localmente sin internet, cuentas ni contraseñas. Servidor Python 3.10+ sin paquetes externos.

Esta distribución crea EjemploCORE con dos servicios, un cliente ficticio y una cotización aceptada que muestra un servicio realizado y un pago parcial. No tiene validez comercial. Cada Core que crees comienza completamente vacío. No contiene el Excel original, clientes reales, bases locales, transcripciones ni capturas. Consulta [cómo subir la carpeta a GitHub](docs/subir-a-github.md).

Estado: MVP para piloto local. Hay casos implementados y probados, casos manuales y funciones pendientes; **no se ha validado una sustitución completa del Excel y de todos los procesos de la transcripción**. La matriz de cobertura detalla esos límites.

## Iniciar

```powershell
.\Start-COREBiller.ps1
```

Abre http://127.0.0.1:8765. Pulsa Crear mi Core para registrar tu espacio vacío y entrar como administrador. Si ya tienes un Core, selecciónalo y elige rol. También puedes usar `python app.py --port 8765`. Ctrl+C detiene el servidor. El lanzador detecta el Python incluido en Codex, después py y python.

Si ejecutas el lanzador otra vez mientras esta copia está abierta, mostrará **COREBiller ya está funcionando** y su dirección. No inicia otro servidor ni modifica las bases. Si el puerto está ocupado por otra aplicación o por una copia de otra carpeta, muestra cómo elegir otro puerto: `.\Start-COREBiller.ps1 -Port 8766`. No cierra procesos automáticamente. Para reiniciar después de actualizar código, detén la instancia anterior con Ctrl+C en su terminal y vuelve a iniciar.

## Recorrido

1. Administrador configura nombre, contacto, condiciones, permisos y logo PNG del Core. EjemploCORE ya incluye un recorrido ficticio.
2. Crea servicios de nombre y código únicos, unidad, tarifa/precio y requisito de inicio. Los CSV en examples son ficticios.
3. Registra o edita clientes y su requisito de inicio particular.
4. Emite cotización con proyecto, responsable, muestras, cantidades, precios personalizados justificados, descuentos por ítem/global y observaciones separadas para PDF y correo.
5. Imprime PDF conjunto o por ítem con márgenes y el logo configurado para ese Core; descarga HTML editable o borrador .eml. Adjunta documentos oficiales y envía el correo manualmente.
6. Registra aceptación. En Seguimiento de servicios registra documentos/pagos y servicios ejecutados.
7. Cada servicio ejecutado reduce la cantidad contratada y el presupuesto de su ítem. Un pago reduce el saldo por cobrar. Se bloquean excesos y falta de requisitos.
8. Corrige/reasigna o anula movimientos con motivo: el original permanece en historial.
9. Consulta informes anuales por institución, servicio o analista y exporta CSV.
10. Descarga una copia SQLite y recupérala en un Core nuevo desde Administración (copias v2 hasta 14 MB).

## Reglas

Precios actualizados manualmente. Las propuestas se pueden guardar como borrador, editar y emitir. Borrar un borrador lo retira de la lista y conserva la auditoría. Las emitidas no se borran ni editan: se cancelan con motivo, incluso si tienen movimientos. Cancelar bloquea nuevos servicios ejecutados, conserva datos y saldos, y permite continuar el seguimiento administrativo; no registra devoluciones ni ajustes financieros. Una ampliación requiere nueva cotización. La vigencia no cambia estados automáticamente.

Cada ítem lleva sus cantidades y dinero. El descuento global se distribuye conservando todos los centavos. La ejecución permite precio acordado neto de descuentos, catálogo actual del servicio ejecutado o precio personalizado con permiso y motivo. COREBiller registra trabajo contratado y ejecutado; no gestiona inventario de suministros.

Inicio: ítem > cliente > servicio. Opciones: ninguno, pago completo, algún pago/anticipo, orden, traslado o autorización. Facturas, órdenes y traslados no cuentan como pago. Se registran referencias y notas, sin almacenar adjuntos ni realizar trámites externos.

En presupuestos multitécnica, cantidad contractual y real ejecutada son campos separados. Contrata un paquete de cantidad 1 y precio exacto; el operador confirma la fracción contractual consumida. No hay equivalencias automáticas entre horas/muestras/paquetes ni transferencia de dinero entre ítems.

## Roles sin autenticación

Administrador configura la matriz de los tres roles. Por defecto: Admin realiza todo; Cotizador maneja clientes, propuestas, ejecución y administración; Consulta lee. Todos tienen permiso de aprobar precios/descuentos, aunque Consulta no emite por defecto. Puede configurarse un rol para ejecutar sin cotizar.

Cualquiera puede elegir cualquier rol. La API aplica permisos, pero no verifica identidad. El nombre es autodeclarado. Sesión local de ocho horas, perdida al reiniciar. Servidor únicamente en 127.0.0.1, con validación de origen y CSRF.

## Preparar el catálogo con Excel o Google Sheets

No necesitas conocimientos técnicos. Sigue estos pasos dentro de COREBiller:

1. Entra al Core que vas a configurar y selecciona el rol **Admin**.
2. Abre **Servicios y tarifas** y pulsa **Importar CSV**.
3. Pulsa **Descargar plantilla CSV**. Se descargará un archivo que puedes abrir con Excel o Google Sheets.
4. En la plantilla, conserva la primera fila y agrega tus servicios debajo: un servicio o tarifa por fila. Llena todas las columnas; en **precio** escribe solo el número, sin `$` ni `COP`.
5. Guarda o descarga una copia en formato **CSV UTF-8**. Si el programa pregunta por el separador, elige coma.
6. Vuelve a COREBiller, selecciona ese archivo y pulsa **Validar e importar**. Si algo no cumple el formato, la aplicación avisará y no aplicará una carga incompleta.
7. Revisa **Servicios y tarifas**. Después ya puedes registrar clientes y crear cotizaciones.

El catálogo debe tener códigos diferentes para identificar los servicios. Si importas otra vez un código existente, COREBiller actualizará ese servicio. Los nombres también deben ser distintos; agrega una aclaración al nombre cuando cambien el año, la modalidad o el alcance. Las cotizaciones ya emitidas conservan el precio con que fueron creadas.

Puedes guardar el archivo en OneDrive o Google Drive si esa carpeta está sincronizada con este computador. Aun así, debes volver a importarlo cuando cambies los precios: COREBiller guarda una copia local y no se actualiza solo. Un enlace web a un Excel o Google Sheet privado no conecta la aplicación automáticamente. Lee la [guía detallada del catálogo y archivos en la nube](docs/configurar-catalogo.md) si necesitas más detalle.

## Datos y respaldo

Bases en data/, independientes por Core. Solo EjemploCORE se crea al estrenar una instalación. Crea tu propio Core desde el selector; su catálogo, clientes y cotizaciones estarán vacíos. Los ejemplos ficticios se importan desde examples/. MicroCore · demostración Excel solo aparece si importas el archivo privado localmente. No se contacta automáticamente a los clientes.

El logo se configura en Administración. Se aceptan archivos PNG de hasta 300 KB y 4000 × 1500 píxeles. Se guarda dentro de la base local del Core y queda capturado en las cotizaciones emitidas; no se envía a servicios externos.

El catálogo importado distingue nombres por tarifa/año y conserva códigos, precios y originales. Las propuestas existentes mantienen su copia anterior. Migrar esquemas antiguos crea respaldo en data/backups/. Copia completa de todos los espacios: detén el servidor y copia data/. CSV no respalda cuentas. No uses SQLite en carpetas sincronizadas o compartidas para varios equipos.

## Excel y sustitución

Datos del Excel permite consulta, copia revisada y migración explícita de cotizaciones/consumos por fila. No se corrigen valores ambiguos por inferencia. Consulta [cobertura y aceptación](docs/casos-microcore.md).

Para sustituir definitivamente el Excel hay que confirmar unidades, tarifas vigentes, saldos de apertura y datos dudosos con MicroCore. Correos, adjuntos y trámites institucionales son manuales. Sin plantilla Word oficial, firma digital, formulario público, portal de resultados, autenticación ni alojamiento compartido. Impresión por ítem conserva una propuesta; no crea consecutivos independientes.

## Verificar

```powershell
python -m unittest discover -s tests -v
```

En esta distribución se ejecutan 26 pruebas operativas y se omite explícitamente 1 prueba del Excel privado, porque el libro no está incluido. Las pruebas operativas no necesitan openpyxl.

Para importar y verificar el Excel en privado, coloca MicroAccounts.xlsx en la raíz e instala la dependencia opcional:

```powershell
python -m pip install -r requirements-excel.txt
python scripts/import_microaccounts.py
```

Después inicia el servidor y ejecuta `python scripts/verify_excel_demo.py` y `python scripts/verify_operational_demo.py`. Estos scripts crean ejemplos en la base microcore-excel; requieren el archivo y base locales y no deben ejecutarse sobre cuentas de producción. El original no se modifica. Bases y resultados quedan excluidos de Git.
