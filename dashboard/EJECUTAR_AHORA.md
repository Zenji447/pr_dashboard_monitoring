# ⚡ EJECUTAR MIGRACIÓN - Checklist Simple

## 🎯 Objetivo
Convertir tu app en multi-tenant (preparada para múltiples clientes)

## ⏱️ Tiempo
2-3 minutos

## 🔒 Seguridad
✅ Backup automático  
✅ Reversible  
✅ Sin pérdida de datos

---

## 📋 PASOS (Copia y pega cada comando)

### 1️⃣ Detener el Servidor
```bash
# Ve a la terminal donde corre (terminal 3)
# Presiona: Ctrl + C
```
✅ Hecho: [ ]

---

### 2️⃣ Ejecutar Migración
```bash
python3 migrations/migrate_to_multi_tenant.py
```
✅ Hecho: [ ]

---

### 3️⃣ Guardar API Key
```
Copia la API Key que aparece en pantalla:
API Key: prm_____________________________

Pégala aquí: _________________________________
```
✅ Guardada: [ ]

---

### 4️⃣ Reiniciar Servidor
```bash
python3 app.py
```
✅ Hecho: [ ]

---

### 5️⃣ Verificar en Navegador
```
Abre: http://localhost:5000
```
✅ Funciona: [ ]

---

## ✅ Verificación Rápida

Marca cada uno:
- [ ] El script terminó sin errores
- [ ] Guardé la API Key
- [ ] El servidor inició
- [ ] Veo mi dashboard
- [ ] Mis PRs aparecen
- [ ] Las configuraciones están

---

## 🎉 ¡Listo!

Si todo está marcado ✅, la migración fue exitosa.

### Siguiente paso:
```bash
git add -A
git commit -m "✅ Migración 001 ejecutada - Multi-tenant funcionando"
```

---

## 🆘 Si algo falla

### Restaurar backup:
```bash
cp ../memoria/state_backup_*.db ../memoria/state.db
python3 app.py
```

### Volver a v4.0:
```bash
git checkout stable-work
python3 app.py
```

---

## 📞 ¿Dudas?

Lee: `GUIA_MIGRACION.md` (guía detallada paso a paso)
