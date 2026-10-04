# MicroCore: cobertura y aceptación del MVP local

COREBiller v2 incorpora el motor operativo de cotizaciones, ejecución, saldos, pagos y correcciones. Reemplazar definitivamente el Excel exige validar unidades, saldos de apertura, documentos y registros ambiguos con MicroCore. Una fila conservada no equivale a una cuenta ya migrada.

Este documento describe la validación realizada en el entorno privado original. El repositorio distribuido no contiene ese Excel, sus datos, capturas ni bases de demostración. Para repetir los ejemplos se necesita importar el archivo privado localmente. Una instalación nueva incluye solo EjemploCORE con datos ficticios; cada nuevo Core comienza vacío.

## Fuente

MicroAccounts.xlsx permanece intacto. SHA-256 verificado: e2601ef69ebb812d5df452fd88b815ea78d87b9c68a7c034a1c6359c70c003fc.

| Fuente | Datos | Tratamiento |
| --- | --- | --- |
| Tarifas | 25 servicios; 24 con cuatro precios numéricos de 2025 | 96 entradas cotizables, nombres identificados por tarifa/año |
| Tarifas históricas | 836 celdas, incluidos ceros/textos | Archivo con coordenadas; no son 836 precios cotizables |
| Copia de BDcotizaciones | 234 filas de 2021; 233 referencias | Consulta y migración por fila revisada |
| BD2021 | 115 servicios históricos | Consulta y migración con elección explícita de cuenta |
| BDcotizaciones, BDservicios | Encabezados sin datos | No se inventan cuentas recientes |
| CuerpoCorreos | Siete celdas de texto | Consulta; borradores nuevos locales |
| Configuración | 57 filas | Conservada para consulta |

122 combinaciones de contacto/institución/correo/identificación, sin fusionar por nombre. Una tarifa adicional reproduce SEM-Tescan de fila 3 de 2021. Unidades importadas: unidad por confirmar, porque el libro no las estructura suficientemente. Los nombres de tarifa ahora son únicos; los snapshots de propuestas previas se conservan.

## Reglas decididas

- Consumo descuenta cantidades y dinero. Pagos llevan otro saldo. Excesos bloqueados por ítem.
- Tarifas actualizadas manualmente; cotización conserva precio acordado.
- Todos los roles aprueban precios/descuentos inicialmente; las demás operaciones dependen de la matriz. Administrador configura permisos. Consulta no emite por defecto.
- Nombres únicos ignorando mayúsculas/espacios repetidos. Variantes descritas en el nombre. Crear variante es distinto de corregir imputación: esta se anula/reasigna con historial.
- Inicio configurable: ítem > cliente > servicio; ninguno, pago, anticipo, orden, traslado o autorización. Requiere cuenta aceptada. Anticipo significa algún pago positivo, sin porcentaje mínimo.

Una orden, factura, traslado o recibo es referencia externa, no pago automático. En cuentas multitécnica puede contratarse cantidad 1 de un paquete por precio exacto; se registran por separado fracción contractual y cantidad real ejecutada. La fracción requiere confirmación manual: no se deducen equivalencias entre horas, muestras y paquetes. No hay bolsa compartida entre ítems.

## Casos de la transcripción

| Caso y evidencia | Estado actual |
| --- | --- |
| Catálogo/tarifas; 2:15 | Operativo. Una entrada por tarifa, nombres únicos. Selección explícita; sin normalizar aliases de cliente automáticamente |
| Cambio anual; 2:15, 28:25 | Manual, como decidió el usuario. Año descriptivo, sin vigencia automática |
| Clientes/autocompletar; 9:51 | Crear/editar contacto, institución, dirección, ciudad, teléfono, identificación. Selección explícita evita mezclar afiliaciones |
| Proyecto/responsable/muestras; 43:23 | Campos en propuesta y documento; sin formulario público |
| Servicios múltiples/descuentos; 17:40 | Descuentos por ítem/global, precio manual y motivo; elegibilidad comercial confirmada por operador |
| Importe exacto 1.750.000 / 1.752.500; 20:05–21:36 | Precio personalizado y cantidad 1, sin cambiar catálogo para obtener el importe |
| Precio fijo/actual/personalizado; 17:12, 28:25 | Operativo en consumos; acordado incluye descuentos |
| Observaciones correo/PDF; 17:12 | Campos separados |
| PDF/condiciones especiales; 31:52 | Impresión conjunta o por ítem; HTML editable, proyecto/responsable. Sin plantilla Word oficial ni firma digital |
| Documento/consecutivo por ítem; Apps Script | Parcial: páginas separadas de una misma propuesta, sin contratos/consecutivos independientes automáticos |
| Información/cotización/muestras/recibo; 15:05, 22:04, 24:03–24:58 | Borrador .eml editable; envío, adjuntos, formato y trámite institucional manuales |
| Aceptación/rechazo; 6:29, 26:15 | Operativo. Los borradores se editan y borran de la lista; las emitidas/aceptadas/rechazadas pueden cancelarse con motivo conservando movimientos |
| Orden/traslado/factura/recibo/pago; columnas AA:AE | Referencia, fecha, monto/notas y anulación con motivo. Sin integrar sistemas ni adjuntar archivos |
| Analista/duración/muestras; 28:25–31:52 | Operativo, cantidades contratadas y ejecutadas separadas |
| Acumulado/saldo; 28:25–28:54 | Saldo por cuenta/ítem, doble límite y protección contra doble gasto simultáneo |
| Cuenta equivocada; 30–32 minutos | Reasignación atómica: anula y reemplaza. Si falla, no altera el original |
| Informes; 26:15 | Año, institución, servicio y analista; aceptado/rechazado/pagos/ejecución, CSV. Cantidades contractuales separadas por unidad. Solo datos operativos |
| Recuperación; 34:12–35:07 | Copia consistente; recuperar en nuevo Core; original conservado. Respaldo automático antes de migrar esquema antiguo |
| Analista sin emitir; posterior a 35:07 | Configurar permisos de Cotizador para ejecutar y desactivar cotización; tres roles fijos |
| Usuario real; 43:52–44:14 | Fuera del alcance sin autenticación. Rol seleccionable, sin comprobar identidad |
| Cualquier Core; 44:14–45:37 | Catálogo/unidades/requisitos/datos independientes. Sin validación con libros reales de MetCore/GeneCore |
| Portal/entrega de resultados; 48:18 | Pendiente, fuera del MVP de cuentas |

## Demostración preparada

Selecciona MicroCore · demostración Excel. Movimientos y documentos de prueba, sin validez comercial.

| Propuesta | Resultado COP |
| --- | --- |
| 0001, reproducción fila 3 SEM-Tescan | 4 × 333.000 = 1.332.000 |
| 0002, SEM externo Tarifas!D3 | 2 × 334.000 = 668.000 |
| 0003, SEM con descuento 15 % | 567.800; consumir 1 deja 1 unidad y 283.900; pago ficticio de 100.000 deja 467.800 por cobrar |
| 0004, dos SEM + oro Tarifas!D25 | 778.000 |
| 0005, presupuesto multitécnica y orden requerida | 1.752.500; SEM ejecutado a 334.000 deja 1.418.500 y fracción contractual 0,8. Orden no cuenta como pago |

Números de la base preparada. Scripts identifican ejemplos por notas si cambia el consecutivo. Notas de ejemplos anteriores permanecen como se emitieron, aunque ahora hay funcionalidades nuevas.

## Migrar el histórico

1. En Datos del Excel abre una fila y comprueba los originales.
2. Revisar / corregir copia: confirma JSON con evidencia/motivo; conserva original.
3. Reabre la fila y usa Migrar registro revisado a operación.
4. Cotización: confirma cliente, servicios, cantidad, precio, descuentos, fecha/vigencia, estado y total. El servidor comprueba el total y evita migrar la misma fila otra vez. Conserva hoja/fila/referencia. Se permite fecha histórica.
5. Servicio: confirma cuenta/ítem, fecha, cantidad contractual/real, analista y precio. Aplican límites y requisitos; una fila solo puede tener un consumo migrado activo.

Revisar no garantiza corrección de los datos: el operador confirma. Documentos/pagos históricos se transcriben manualmente desde originales. Migración fallida no modifica saldos.

## Datos que requieren confirmación

- Tarifas disponibles hasta 2025, no certificadas como vigentes en 2026.
- Mantenimiento: COP -, requiere precio confirmado, no se interpreta como cero.
- Filas 2, 116, 187, 201, 218: cantidad × precio difiere del total. No se infieren ajustes/descuentos. 44378/44302 podrían ser fechas serializadas, sin reinterpretarlas automáticamente.
- U0621-0001 aparece en dos filas; se conservan/migran por fila, sin fusionarlas por referencia.
- Tipos de cliente y fechas heterogéneos, selección/confirmación explícitas.
- Faltan formato de muestras, plantilla Word y documentos completos referenciados en Drive.
- No vienen las cuentas recientes utilizadas en la reunión.

## Evidencia técnica

16 pruebas automatizadas en el entorno original: precios/copias inmutables, CSV transaccional, aislamiento/roles/CSRF; 96 precios contrastados contra Excel y checksum; redondeo/descuentos, doble saldo y doble límite; concurrencia; anulación/reasignación con reversión; pagos/requisitos; permisos/nombres; copia revisada y migración explícita no repetible; respaldo/recuperación. La distribución sin datos privados ejecuta 25 y omite explícitamente la prueba dependiente del Excel. Estas pruebas no certifican todos los casos de la transcripción.

Scripts verify_excel_demo.py y verify_operational_demo.py dejan resultados en outputs/. El segundo comprueba presupuesto exacto, requisito de orden, ejecución a tarifa del libro y conservación de fuente. En navegador se verificaron consumo parcial de 0003 y pago separado.

Antes de retirar Excel: ejecutar casos reales en paralelo, confirmar unidades/tarifas y saldos de apertura, revisar cada inconsistencia y aprobar documento comercial y pasos manuales externos. Este MVP soporta ese piloto, no certifica los datos históricos ni sustituye integraciones institucionales.
