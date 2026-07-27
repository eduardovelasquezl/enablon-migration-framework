# Sprint Review Template — EMF

**Status:** Approved Design. Copiar este fichero como
`docs/05-sprint-reviews/sprint-review-<identificador>.md` al cerrar cada
incremento (sprint) sobre EMF o sobre cualquier proyecto construido sobre
EMF. No se rellena "a posteriori" de memoria — se completa con la
evidencia real generada durante el sprint (salida de `git status`, de
`pytest`, artefactos escritos).

---

## Sprint: `<nombre-del-sprint>`

**Fecha:** `<AAAA-MM-DD>`
**Rama:** `<nombre-de-rama>`
**Fase del roadmap relacionada:** `<Fase Pn — ver docs/04-roadmap/roadmap.md, o "N/A" si es un incremento sobre el proyecto Moeve, no sobre EMF>`

## 1. Objetivo del sprint

`<qué se pidió construir/diseñar, en una o dos frases>`

## 2. Alcance aprobado

`<lista exacta de lo que se autorizó — copiar del encargo original, no
parafrasear>`

## 3. Explícitamente fuera de alcance

`<lista de lo que NO debía tocarse en este sprint>`

## 4. Capa afectada (Blueprint § 6)

`<Core / Engine / Connector / Plugin / Project Configuration / Documentación
— si toca más de una capa, justificar por qué no viola la dirección de
dependencia>`

## 5. Archivos creados

```
<lista exacta>
```

## 6. Archivos modificados

```
<lista exacta>
```

## 7. Archivos explícitamente no modificados (si el encargo lo exigía)

`<lista de componentes protegidos, con confirmación de que siguen intactos>`

## 8. Resultado de la suite de pruebas

```
<salida real de `pytest tests/ -q`, passed/skipped, nunca inventada>
```

## 9. Resultado de `git status` / `git diff --stat`

```
<salida real, no resumida de memoria>
```

## 10. Principios verificados

`<marcar cuáles de los 14 principios del Blueprint aplican a este sprint y
cómo se cumplieron — en particular, si el sprint tocó el Core, confirmar
explícitamente principio 9 (No Higher-Layer Dependencies in Core)>`

## 11. ADR creadas o referenciadas

`<lista, con enlace relativo>`

## 12. Supuestos realizados

`<cualquier decisión tomada sin confirmación explícita del encargo, con su
justificación>`

## 13. Riesgos o cuestiones abiertas

`<qué queda pendiente de decidir, qué podría romperse en un sprint
posterior si no se resuelve>`

## 14. Confirmaciones de seguridad

- [ ] No se ejecutó ninguna operación de escritura contra ninguna fuente real.
- [ ] No se expuso ninguna credencial en código, log, manifiesto o este
      documento.
- [ ] No se realizó ningún commit/push sin autorización explícita.
- [ ] No se modificó `.env` ni ningún fichero de configuración con
      credenciales.

## 15. Recomendación de siguiente paso

`<qué sprint/fase debería seguir a este, y qué debe estar resuelto antes de
empezarlo>`

## 16. Aprobación

`<quién aprobó el cierre de este sprint y cuándo — este documento no se
considera cerrado hasta que exista esa aprobación explícita>`
