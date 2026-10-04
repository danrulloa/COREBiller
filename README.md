# COREBiller local · MVP v3

Herramienta genérica para Core Facilities. Catálogo, clientes, cotizaciones, consumos, pagos, correcciones e informes; base SQLite independiente por Core. Funciona localmente sin internet, cuentas ni contraseñas. Servidor Python 3.10+ sin paquetes externos.

Esta distribución crea únicamente EjemploCORE, con dos servicios y un cliente ficticios, sin cotizaciones. Cada Core que crees comienza completamente vacío. No contiene el Excel original, clientes reales, bases locales, transcripciones ni capturas. Consulta [cómo subir la carpeta a GitHub](docs/subir-a-github.md).

Estado: MVP para piloto local. Hay casos implementados y probados, casos manuales y funciones pendientes; **no se ha validado una sustitución completa del Excel y de todos los procesos de la transcripción**. La matriz de cobertura detalla esos límites.

## Iniciar

```powershell
.\Start-COREBiller.ps1
```

Abre http://127.0.0.1:8765. Pulsa Crear mi Core para registrar tu espacio vacío y entrar como administrador. Si ya tienes un Core, selecciónalo y elige rol. También puedes usar `python app.py --port 8765`. Ctrl+C detiene el servidor. El lanzador detecta el Python incluido en Codex, después py y python.

## Recorrido

1. Administrador configura nombre, contacto, condiciones y permisos.
2. Crea servicios de nombre y código únicos, unidad, tarifa/precio y requisito de inicio. Los CSV en examples son ficticios.
3. Registra o edita clientes y su requisito de inicio particular.
4. Emite cotización con proyecto, responsable, muestras, cantidades, precios personalizados justificados, descuentos por ítem/global y observaciones separadas para PDF y correo.
5. Imprime PDF conjunto o por ítem; descarga HTML editable o borrador .eml. Adjunta documentos oficiales y envía el correo manualmente.
6. Registra aceptación. Abre Cuentas y consumos, registra documentos/pagos y ejecución.
7. Un consumo reduce cantidad y presupuesto del ítem. Un pago reduce saldo por cobrar. Se bloquean excesos y falta de requisitos.
8. Corrige/reasigna o anula movimientos con motivo: el original permanece en historial.
9. Consulta informes anuales por institución, servicio o analista y exporta CSV.
10. Descarga una copia SQLite y recupérala en un Core nuevo desde Administración (copias v2 hasta 14 MB).

## Reglas

Precios actualizados manualmente. Las propuestas se pueden guardar como borrador, editar y emitir. Borrar un borrador lo retira de la lista y conserva la auditoría. Las emitidas no se borran ni editan: se cancelan con motivo, incluso si tienen movimientos. Cancelar bloquea nuevos consumos, conserva datos y saldos, y permite continuar el seguimiento administrativo; no registra devoluciones ni ajustes financieros. Una ampliación requiere nueva cotización. La vigencia no cambia estados automáticamente.

Cada ítem lleva sus cantidades y dinero. El descuento global se distribuye conservando todos los centavos. La ejecución permite precio acordado neto de descuentos, catálogo actual del servicio ejecutado o precio personalizado con permiso y motivo.

Inicio: ítem > cliente > servicio. Opciones: ninguno, pago completo, algún pago/anticipo, orden, traslado o autorización. Facturas, órdenes y traslados no cuentan como pago. Se registran referencias y notas, sin almacenar adjuntos ni realizar trámites externos.

En presupuestos multitécnica, cantidad contractual y real ejecutada son campos separados. Contrata un paquete de cantidad 1 y precio exacto; el operador confirma la fracción contractual consumida. No hay equivalencias automáticas entre horas/muestras/paquetes ni transferencia de dinero entre ítems.

## Roles sin autenticación

Administrador configura la matriz de los tres roles. Por defecto: Admin realiza todo; Cotizador maneja clientes, propuestas, ejecución y administración; Consulta lee. Todos tienen permiso de aprobar precios/descuentos, aunque Consulta no emite por defecto. Puede configurarse un rol para ejecutar sin cotizar.

Cualquiera puede elegir cualquier rol. La API aplica permisos, pero no verifica identidad. El nombre es autodeclarado. Sesión local de ocho horas, perdida al reiniciar. Servidor únicamente en 127.0.0.1, con validación de origen y CSRF.

## Catálogo y respaldo

CSV UTF-8, coma, encabezados `code,name,unit,category,price`, precio COP con punto decimal. Código existente actualiza; nombres únicos ignorando mayúsculas y espacios repetidos. Identifica variantes/tarifas en el nombre. Importación inválida revierte todos los cambios.

Bases en data/, independientes por Core. Solo EjemploCORE se crea al estrenar una instalación. Crea tu propio Core desde el selector; su catálogo, clientes y cotizaciones estarán vacíos. Los ejemplos ficticios se importan desde examples/. MicroCore · demostración Excel solo aparece si importas el archivo privado localmente. No se contacta automáticamente a los clientes.

El catálogo importado distingue nombres por tarifa/año y conserva códigos, precios y originales. Las propuestas existentes mantienen su copia anterior. Migrar esquemas antiguos crea respaldo en data/backups/. Copia completa de todos los espacios: detén el servidor y copia data/. CSV no respalda cuentas. No uses SQLite en carpetas sincronizadas o compartidas para varios equipos.

## Excel y sustitución

Datos del Excel permite consulta, copia revisada y migración explícita de cotizaciones/consumos por fila. No se corrigen valores ambiguos por inferencia. Consulta [cobertura y aceptación](docs/casos-microcore.md).

Para sustituir definitivamente el Excel hay que confirmar unidades, tarifas vigentes, saldos de apertura y datos dudosos con MicroCore. Correos, adjuntos y trámites institucionales son manuales. Sin plantilla Word oficial, firma digital, formulario público, portal de resultados, autenticación ni alojamiento compartido. Impresión por ítem conserva una propuesta; no crea consecutivos independientes.

## Verificar

```powershell
python -m unittest discover -s tests -v
```

En esta distribución se ejecutan 22 pruebas operativas y se omite explícitamente 1 prueba del Excel privado, porque el libro no está incluido. Las pruebas operativas no necesitan openpyxl.

Para importar y verificar el Excel en privado, coloca MicroAccounts.xlsx en la raíz e instala la dependencia opcional:

```powershell
python -m pip install -r requirements-excel.txt
python scripts/import_microaccounts.py
```

Después inicia el servidor y ejecuta `python scripts/verify_excel_demo.py` y `python scripts/verify_operational_demo.py`. Estos scripts crean ejemplos en la base microcore-excel; requieren el archivo y base locales y no deben ejecutarse sobre cuentas de producción. El original no se modifica. Bases y resultados quedan excluidos de Git.
