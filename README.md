# Power Pricing — Integración para Home Assistant

Integración personalizada para Home Assistant que permite configurar distintos tipos de tarifas eléctricas y obtener el precio actual de la electricidad como sensor.

## Tipos de tarifa soportados

| Tipo | Descripción |
|------|-------------|
| **Precio fijo** | Un único precio constante en €/kWh |
| **Por tramos (TOU)** | Distintos precios según la hora del día (hasta 6 tramos) |
| **PVPC** | Precio Voluntario para el Pequeño Consumidor — datos en tiempo real de REE |
| **Indexada** | Precio de mercado (PVPC) con multiplicador y margen fijo aplicados |

## Instalación

### Vía HACS (recomendado)
1. Abre HACS → Integraciones → ⋮ → Repositorios personalizados
2. Añade la URL de este repositorio y selecciona categoría **Integración**
3. Instala **Power Pricing**
4. Reinicia Home Assistant

### Manual
1. Copia la carpeta `power_pricing` en `config/custom_components/`
2. Reinicia Home Assistant

## Configuración

Ve a **Ajustes → Dispositivos y servicios → Añadir integración** y busca **Power Pricing**.

El asistente te guiará por los pasos según el tipo de tarifa elegido.

### Tarifa fija
Solo necesitas introducir el precio en €/kWh.

### Por tramos horarios (TOU)
1. Indica cuántos tramos tiene tu tarifa (1–6)
2. Para cada tramo: hora de inicio, hora de fin y precio

> Los tramos se definen en formato `HH:MM`. El último tramo debe cubrir hasta las `00:00` del día siguiente.

### PVPC
Conecta directamente con la API de Red Eléctrica de España para obtener el precio horario en tiempo real.

### Indexada
Aplica un multiplicador y un margen fijo sobre el precio PVPC:

```
precio_final = precio_pvpc × multiplicador + margen_fijo
```

## Sensores creados

Según el tipo de tarifa configurado se crearán los siguientes sensores:

- `sensor.power_pricing_<nombre>_current_price` — Precio actual en €/kWh

## Requisitos

- Home Assistant 2023.6 o superior
- Python 3.11+

## Contribuir

Las contribuciones son bienvenidas. Por favor abre un issue antes de enviar un PR con cambios grandes.

## Licencia

MIT
