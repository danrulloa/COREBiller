# Configurar el catálogo de servicios

El catálogo define los servicios, unidades, categorías y precios que el Core puede cotizar. Cada Core tiene su propio catálogo. La plantilla descargable es CSV y se puede abrir y editar con Excel o Google Sheets.

## Columnas

| Columna | Obligatoria | Cómo llenarla |
| --- | --- | --- |
| `code` | Sí | Código estable y único del servicio o variante, por ejemplo `MET-001`. Si se vuelve a importar el mismo código, COREBiller actualiza ese registro. |
| `name` | Sí | Nombre claro del servicio. Distingue variantes con una nota concreta, como año, matriz, modalidad o alcance. Los nombres duplicados no se permiten. |
| `unit` | Sí | Unidad que se cotiza, por ejemplo `muestra`, `hora`, `corrida` o `análisis`. |
| `category` | Sí | Tipo de tarifa o clasificación que ayuda a distinguir el servicio, por ejemplo `Tarifa 2026` o `Investigación`. |
| `price` | Sí | Precio en COP como número, con punto para decimales; por ejemplo `125000` o `125000.50`. No escribas `$`, `COP` ni separadores de miles. |

Cada fila representa una combinación de servicio y tarifa. Si cambia el precio por año o por modalidad, crea una entrada claramente diferenciada, con código propio y un nombre/categoría que evite confusiones. No reutilices el mismo nombre para dos servicios distintos.

## Preparar e importar

1. Entra al Core y abre **Servicios y tarifas** con el rol Administrador.
2. Pulsa **Importar CSV** y descarga `COREBiller-plantilla-catalogo.csv`.
3. Ábrelo en Excel o Google Sheets. Conserva exactamente los encabezados y agrega una fila por servicio.
4. Guarda o descarga el archivo como **CSV UTF-8 delimitado por comas**. Si Excel ofrece varios formatos CSV, elige el que indique UTF-8. No uses punto y coma como separador.
5. Regresa a COREBiller, selecciona el CSV y pulsa **Validar e importar**. Si hay una fila inválida o un nombre duplicado, la importación completa se revierte para evitar una carga parcial.
6. Revisa el catálogo en **Servicios y tarifas** antes de emitir cotizaciones.

La importación agrega códigos nuevos y actualiza los existentes. No elimina servicios que ya no estén en el archivo; desactívalos o edítalos en el catálogo. Las cotizaciones existentes conservan su copia de nombres, unidades y precios.

## Usarlo con archivos en la nube

Puedes guardar el CSV en una carpeta de OneDrive, Google Drive para escritorio u otro servicio que sincronice archivos en este computador. Para importar, descarga o selecciona la copia local sincronizada en la pantalla de COREBiller. La sincronización de carpetas mantiene el archivo en la nube, pero COREBiller importa una copia de sus datos a la base local: cambiar el CSV no actualiza el catálogo hasta volver a importarlo.

Pegar un enlace privado de Excel Online o Google Sheets no basta para que la aplicación lo lea. Una conexión directa necesitaría integrar el proveedor elegido y su autorización; el MVP no solicita credenciales de Microsoft o Google ni escribe de vuelta a la hoja. Mientras COREBiller corre en un computador local, la base de datos operativa permanece en ese computador.

Esta plantilla cubre **servicios y tarifas**. Clientes, condiciones comerciales y logo del Core se configuran en sus pantallas de COREBiller; no se importan desde este CSV.
