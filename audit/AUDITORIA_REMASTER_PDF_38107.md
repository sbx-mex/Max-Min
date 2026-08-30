# Auditoría Remaster PDF · 38107 Pedregal

Fecha de corte: 30/08/2026  
Repositorio verificado: `sbx-mex/Max-Min`, rama `main`, commit descargado `434d16f`.

## Dictamen

La carga nueva es íntegra y consistente con el plan: 954 archivos JSON de tienda distribuidos en 12 carpetas, semanas 1-34 y cruce CeCo → Tienda activo. Pedregal 38107 reconcilia exactamente 1,219 registros de semanas 18-25 contra el ZIP fuente: 0 faltantes, 0 extras y 0 diferencias de valor.

La exportación revisada genera Carta horizontal en cuadrícula 4 × 3, con 12 etiquetas por hoja y continuación automática. La muestra utiliza 15 etiquetas: 12 en la página 1 y 3 en la página 2.

## Hallazgos y resolución

| Área | Hallazgo | Resolución |
|---|---|---|
| Cabecera PDF | Ocupaba demasiado alto para información secundaria. | Una sola fila compacta de 8 mm: Tienda, Semanas y Actualización. |
| Descripción SAP | Correcta, pero sin suficiente prioridad visual. | Tipografía grande con ajuste dinámico de una o dos líneas. |
| Identidad | Nombre Inventario y DIA eran demasiado pequeños; faltaba #SAP. | Línea exclusiva `Nombre Inventario | #DIA | #SAP`; #SAP usa el campo `ID WOE` del catálogo. |
| MIN / MAX | Valores válidos. | Se conservan centrados y se aumenta su jerarquía. |
| Pie | Formato, presentación y pedidos estaban comprimidos. | Tres celdas: Unidad/Pick Pack, Unidad de medida y # Pedidos. |
| Multipágina | La validación solo comprobaba orientación y tamaño. | Python valida páginas, campos obligatorios, 12 etiquetas máximas, cabecera única, render, márgenes y cobertura visual. |
| Motor anterior | Persisten 17 archivos obsoletos en GitHub. | Se entrega lista exacta de borrado; el workflow manual existente puede retirarlos de forma segura. |

## Evidencia de datos

- Directorio: 968 CeCo; 954 con datos y 14 sin registros en la fuente.
- Ingredientes: 701; descripciones SAP encontradas: 626; formatos confirmados: 594.
- Indicadores no vacíos: 0, conforme a la fuente.
- Registros positivos: 4,764,428.
- Carpetas: `stores_01` a `stores_11` contienen 80 archivos cada una; `stores_12` contiene 74.
- Carpeta de datos más pesada: `stores_03`, 4,298,380 bytes; debajo del límite de 25 MB.
- Ninguna carpeta supera 100 archivos.

## Evidencia PDF

- Tamaño por página: 792 × 612 pt, Carta horizontal.
- Páginas: 2.
- Etiquetas: 15, distribución 12 + 3.
- Cabecera: exactamente una por página.
- Render de control: 180 dpi.
- Márgenes mínimos detectados: 27 px; ningún elemento toca el borde de corte.
- Campos verificados: Descripción SAP, Nombre Inventario, #DIA, #SAP, MIN, MAX, Formato, Unidad de medida y # Pedidos.

## Riesgo pendiente antes de publicar

El código nuevo no utiliza los motores anteriores, pero la rama remota aún conserva sus archivos. Ejecuta el workflow manual **Limpiar motores obsoletos** o elimina exactamente los elementos listados en `BORRAR_EN_GITHUB.txt`; después ejecuta **Validar Max Min Remaster**. No se requiere volver a cargar `data/`.
