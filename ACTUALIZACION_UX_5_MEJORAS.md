# Actualización UX — ruta intuitiva

Base validada: `63173eb` de `main`.

## Subida

1. Descomprime el ZIP.
2. Arrastra todas las rutas a la raíz del repositorio, conservando sus carpetas.
3. Confirma la sustitución de los archivos existentes.
4. Espera a que termine **Validar Max Min Remaster**.

No se incluyen CSV ni archivos de tiendas: este paquete sólo corrige navegación, diseño y auditoría.

## Resultado esperado

- El botón global de PDF se elimina del encabezado.
- Cada pestaña muestra una ruta de cuatro pasos y resalta el avance actual.
- En Consulta, **Lista PDF** exporta siempre las filas filtradas y no requiere selección.
- Para etiquetas, **Elegir visibles** sustituye cualquier selección anterior; después se habilita **Exportar etiquetas**.
- Etiquetas, Consulta y Acomodo conservan instrucciones breves dentro de su contexto.
- `tools/audit_experience.py` impide que la ubicación y el orden de estas acciones se pierdan en futuras cargas.

## Validación local opcional

```bash
node --check js/app.js
node --check sw.js
python tools/audit_project.py
python tools/audit_experience.py
```
