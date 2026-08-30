# Actualización UX - 5 mejoras

Base validada: `057a17e` de `main`.

## Subida

1. Descomprime el ZIP.
2. Arrastra todas las rutas a la raíz del repositorio, conservando sus carpetas.
3. Confirma la sustitución de los archivos existentes.
4. Espera a que termine **Validar Max Min Remaster**.

No se incluyen CSV, directorios ni archivos de tiendas: este paquete sólo corrige la experiencia y las auditorías.

## Resultado esperado

- Consulta con nueve columnas: Sel., Ingrediente / SAP, Categoría, #DIA, #SAP, Uso prom., Mín., Máx. y Estado.
- Catálogo, Consulta y PDFs sin valores visibles iguales a cero.
- Selector entre Lista operativa PDF y Etiquetas de rack PDF.
- Acomodo 60/40 con arrastre, toque y ajuste de marcadores sobre la foto.
- Auditoría Python de las cinco mejoras y render de ambas exportaciones.

## Validación local opcional

```bash
python tools/verify_upload_patch.py
python tools/audit_experience.py
```

