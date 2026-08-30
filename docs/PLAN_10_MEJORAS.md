# Diez mejoras aplicadas

1. **Limpieza controlada:** workflow único para retirar 17 artefactos obsoletos y validar antes de publicar.
2. **Menos ruido en Actions:** concurrencia que cancela validaciones anteriores cuando llegan cargas consecutivas.
3. **Actualización incremental:** Semana 35 se incorpora sin reconstruir las semanas 1-34.
4. **Entrada protegida:** sólo se aceptan fuentes dentro de `updates/incoming/`, en CSV o ZIP.
5. **Validación transaccional:** no se escribe información hasta validar encabezados, semanas, CeCo, Indicadores y valores.
6. **Datos siempre frescos:** estrategia network-first para manifiesto y tiendas; evita semanas antiguas atrapadas en caché.
7. **Semanas rápidas:** accesos a Última, Últimas 4 y Últimas 8.
8. **Filtros legibles:** resumen activo y búsqueda por Ingrediente, Descripción, #DIA o #SAP.
9. **Ayuda discreta:** manual implícito de tres pasos dentro de la pantalla principal.
10. **Recuperación clara:** reintento de carga de tienda, timeout y mensajes operativos sin lenguaje técnico.
