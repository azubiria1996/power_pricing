"""Constantes para la integración Power Pricing."""
from typing import Final

DOMAIN: Final = "power_pricing"

# ---------------------------------------------------------------------------
# Tipos de tarifa soportados
# ---------------------------------------------------------------------------
TARIFF_FIXED: Final = "fixed"
TARIFF_TOU: Final = "time_of_use"
TARIFF_PVPC: Final = "pvpc"
TARIFF_INDEXED: Final = "indexed"

TARIFF_TYPES: Final = [
    TARIFF_FIXED,
    TARIFF_TOU,
    TARIFF_PVPC,
    TARIFF_INDEXED,
]

TARIFF_TYPE_LABELS: Final = {
    TARIFF_FIXED:   "Precio fijo",
    TARIFF_TOU:     "Por tramos horarios",
    TARIFF_PVPC:    "PVPC (España)",
    TARIFF_INDEXED: "Indexada",
}

# ---------------------------------------------------------------------------
# Claves de configuración — comunes
# ---------------------------------------------------------------------------
CONF_TARIFF: Final = "tariff"
CONF_TYPE: Final = "type"
CONF_PARAMETERS: Final = "parameters"
CONF_ENTRY_NAME: Final = "entry_name"

CONF_CURRENCY: Final = "currency"
CONF_TIMEZONE: Final = "timezone"

# ---------------------------------------------------------------------------
# Tarifa fija
# ---------------------------------------------------------------------------
CONF_PRICE: Final = "price"

# ---------------------------------------------------------------------------
# Time of use (TOU)
# ---------------------------------------------------------------------------
CONF_BLOCKS: Final = "blocks"
CONF_NAME: Final = "name"
CONF_START: Final = "start"
CONF_END: Final = "end"
CONF_NUM_BLOCKS: Final = "num_blocks"

TOU_MIN_BLOCKS: Final = 1
TOU_MAX_BLOCKS: Final = 6

# ---------------------------------------------------------------------------
# Indexada
# ---------------------------------------------------------------------------
CONF_BASE: Final = "base"
CONF_MULTIPLIER: Final = "multiplier"
CONF_FIXED_MARKUP: Final = "fixed_markup"
CONF_EXTRA_COSTS: Final = "extra_costs"
CONF_VALUE: Final = "value"

# ---------------------------------------------------------------------------
# PVPC / fuente de datos
# ---------------------------------------------------------------------------
CONF_SOURCE: Final = "source"
PVPC_SOURCE_OFFICIAL: Final = "official"

PVPC_SOURCE_LABELS: Final = {
    PVPC_SOURCE_OFFICIAL: "Oficial (REE - Red Eléctrica de España)",
}

# ---------------------------------------------------------------------------
# Fuentes base para tarifa indexada
# ---------------------------------------------------------------------------
INDEXED_BASE_PVPC: Final = "pvpc"

INDEXED_BASE_LABELS: Final = {
    INDEXED_BASE_PVPC: "PVPC (Red Eléctrica de España)",
}

# ---------------------------------------------------------------------------
# Valores por defecto
# ---------------------------------------------------------------------------
DEFAULT_MULTIPLIER: Final = 1.0
DEFAULT_FIXED_MARKUP: Final = 0.0
DEFAULT_NUM_BLOCKS: Final = 3
