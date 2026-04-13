# ⚡ Power Pricing for Home Assistant
 
<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-blue" />
  <img src="https://img.shields.io/badge/HA-2024.1%2B-green" />
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" />
  <img src="https://img.shields.io/badge/HACS-custom-orange" />
</p>
 
> Integración personalizada para Home Assistant que permite configurar cualquier tipo de tarifa eléctrica española y obtener el precio actual en tiempo real, sin necesidad de tokens ni registros externos.
 
---
 
## 🌟 ¿Qué hace Power Pricing?
 
Power Pricing nació como alternativa a la integración oficial `pvpc_hourly_pricing` de Home Assistant, que lleva tiempo con problemas de compatibilidad. Va más allá: soporta **cuatro tipos de tarifa** distintos y expone sensores con estadísticas completas del día, pensados para usarse directamente en automatizaciones.
 
- **Sin tokens ni registros** — los precios PVPC se obtienen automáticamente de Red Eléctrica de España
- **Cuatro tipos de tarifa** — fija, por tramos, PVPC e indexada
- **Estadísticas completas** — mínimo, máximo, media, horas baratas y serie horaria completa
- **Listo para automatizaciones** — atributos `is_cheap` y `price_ratio` para controlar electrodomésticos
- **Datos de mañana** — disponibles cada día a partir de las ~20:15h
 
---
 
## ✨ Tipos de tarifa soportados
 
| Tipo | Descripción |
|------|-------------|
| **Precio fijo** | Un único precio constante en €/kWh |
| **Por tramos (TOU)** | Distintos precios según la hora del día, hasta 6 tramos configurables |
| **PVPC** | Precio Voluntario para el Pequeño Consumidor — datos en tiempo real de REE |
| **Indexada** | Precio de mercado (PVPC) con multiplicador y margen fijo aplicados |
 
---
 
## 📱 Sensores creados
 
Por cada tarifa configurada se crean **4 sensores**:
 
| Sensor | Estado | Descripción |
|--------|--------|-------------|
| `sensor.power_pricing_<nombre>_precio_actual` | `0.12345 EUR/kWh` | Precio en la hora actual |
| `sensor.power_pricing_<nombre>_minimo_hoy` | `0.08123 EUR/kWh` | Precio mínimo del día |
| `sensor.power_pricing_<nombre>_maximo_hoy` | `0.21456 EUR/kWh` | Precio máximo del día |
| `sensor.power_pricing_<nombre>_media_hoy` | `0.13200 EUR/kWh` | Precio medio del día |
 
### Atributos del sensor de precio actual
 
| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `today_min` | float | Precio mínimo del día en €/kWh |
| `today_min_at` | string | Hora del precio mínimo (`"04:00"`) |
| `today_max` | float | Precio máximo del día en €/kWh |
| `today_max_at` | string | Hora del precio máximo (`"20:00"`) |
| `today_mean` | float | Precio medio del día en €/kWh |
| `today_cheap_hours` | list | Horas por debajo de la media, ordenadas de más barata a más cara |
| `today_prices` | dict | Serie completa `{"00:00": 0.123, ..., "23:00": 0.098}` |
| `is_cheap` | bool | `true` si el precio actual está por debajo de la media |
| `price_ratio` | float | Posición del precio actual en el rango del día (0.0 = mínimo, 1.0 = máximo) |
| `tomorrow_min` | float | Precio mínimo de mañana (disponible tras ~20:15h) |
| `tomorrow_min_at` | string | Hora del precio mínimo de mañana |
| `tomorrow_max` | float | Precio máximo de mañana |
| `tomorrow_max_at` | string | Hora del precio máximo de mañana |
| `tomorrow_mean` | float | Precio medio de mañana |
| `tomorrow_prices` | dict | Serie completa de mañana |
 
---
 
## 💡 Ejemplos de automatización
 
**Activar el lavavajillas solo cuando el precio está por debajo de la media:**
```yaml
trigger:
  - platform: template
    value_template: "{{ state_attr('sensor.power_pricing_pvpc_precio_actual', 'is_cheap') }}"
action:
  - service: switch.turn_on
    target:
      entity_id: switch.lavavajillas
```
 
**Notificación diaria con el precio mínimo de mañana:**
```yaml
trigger:
  - platform: time
    at: "22:30:00"
action:
  - service: notify.mobile_app_tu_telefono
    data:
      message: >
        💡 El mejor precio de mañana es
        {{ state_attr('sensor.power_pricing_pvpc_precio_actual', 'tomorrow_min') }} €/kWh
        a las {{ state_attr('sensor.power_pricing_pvpc_precio_actual', 'tomorrow_min_at') }}h.
```
 
**Cargar el coche eléctrico en la hora más barata del día:**
```yaml
trigger:
  - platform: template
    value_template: >
      {{ now().strftime('%H:00') ==
         state_attr('sensor.power_pricing_pvpc_precio_actual', 'today_min_at') }}
action:
  - service: switch.turn_on
    target:
      entity_id: switch.cargador_coche
```
 
---
 
## 🚀 Instalación
 
### Vía HACS (recomendado)
1. Abre HACS → Integraciones → ⋮ → Repositorios personalizados
2. Añade la URL de este repositorio y selecciona categoría **Integración**
3. Instala **Power Pricing**
4. Reinicia Home Assistant
 
### Manual
1. Descarga o clona este repositorio
2. Copia la carpeta `power_pricing` en `config/custom_components/`
3. Reinicia Home Assistant
 
---
 
## ⚙️ Configuración
 
Ve a **Ajustes → Dispositivos y servicios → Añadir integración** y busca **Power Pricing**.
 
Puedes configurar tantas tarifas como quieras — cada una genera su propio conjunto de sensores.
 
### Tarifa fija
Introduce el precio en €/kWh. El sensor mostrará siempre ese valor.
 
### Por tramos horarios (TOU)
1. Elige cuántos tramos tiene tu tarifa (1–6)
2. Para cada tramo define: hora de inicio, hora de fin y precio
 
> Los tramos se definen en formato `HH:MM`. Se soportan tramos que cruzan la medianoche (ej. `22:00` → `06:00`).
 
### PVPC
Selecciona tu zona geográfica. Los precios se descargan automáticamente de Red Eléctrica de España cada hora. **No necesitas ningún token.**
 
| Zona | Territorios |
|------|-------------|
| PCB | Península, Canarias y Baleares |
| CYM | Ceuta y Melilla |
 
### Indexada
Aplica un multiplicador y un margen fijo sobre el precio PVPC de REE:
 
```
precio_final = precio_pvpc × multiplicador + margen_fijo
```
 
Útil para comercializadoras indexadas que aplican un porcentaje o margen fijo sobre el pool.
 
---
 
## 📋 Requisitos
 
| Componente | Versión mínima |
|-----------|---------------|
| Home Assistant | 2024.1.0 |
| Python | 3.11+ |
 
No requiere dependencias externas ni add-ons adicionales.
 
---
 
## 🔧 Solución de problemas
 
**Power Pricing no aparece en el buscador de integraciones**
> Asegúrate de que la carpeta `power_pricing` está en `config/custom_components/` y reinicia HA completamente con `ha host reboot`.
 
**Los sensores aparecen como `unavailable`**
> Comprueba los logs en **Ajustes → Sistema → Logs** filtrando por `power_pricing`. Lo más habitual es un problema de conexión a internet al contactar con `api.preciodelaluz.org`.
 
**Los precios de mañana no aparecen**
> Red Eléctrica publica los precios del día siguiente cada día a las ~20:15h. Antes de esa hora es normal que los atributos `tomorrow_*` no estén disponibles.
 
**El precio actual es `unknown`**
> Puede ocurrir si los datos de la hora actual no están disponibles en la API. El coordinator reintenta automáticamente en el siguiente ciclo (cada 60 minutos).
 
---
 
## 🗺️ Roadmap
 
- [ ] Options flow — editar la tarifa sin borrar y recrear la entrada
- [ ] Soporte HACS oficial
- [ ] Sensor binario `is_cheap` como entidad independiente
- [ ] Tests unitarios
 
---
 
## 📜 Licencia
 
MIT License — Ander Zubiria
 
---
 
## ☕ Apoya el proyecto
 
Si Power Pricing te resulta útil, puedes apoyar el desarrollo:
 
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/anderzubiria)
