"""Config flow para Power Pricing."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BASE,
    CONF_BLOCKS,
    CONF_END,
    CONF_ENTRY_NAME,
    CONF_FIXED_MARKUP,
    CONF_GEO_ZONE,
    CONF_MULTIPLIER,
    CONF_NAME,
    CONF_NUM_BLOCKS,
    CONF_PARAMETERS,
    CONF_PRICE,
    CONF_START,
    CONF_TARIFF,
    CONF_TYPE,
    DEFAULT_FIXED_MARKUP,
    DEFAULT_MULTIPLIER,
    DEFAULT_NUM_BLOCKS,
    DOMAIN,
    GEO_ZONE_LABELS,
    GEO_ZONE_PCB,
    INDEXED_BASE_LABELS,
    TARIFF_FIXED,
    TARIFF_INDEXED,
    TARIFF_PVPC,
    TARIFF_TOU,
    TARIFF_TYPE_LABELS,
    TOU_MAX_BLOCKS,
    TOU_MIN_BLOCKS,
)

# ---------------------------------------------------------------------------
# Helpers de validación
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _validate_time(value: str) -> str:
    """Valida formato HH:MM (00:00 – 23:59)."""
    if not _TIME_RE.match(value.strip()):
        raise vol.Invalid("Formato inválido. Usa HH:MM (ej. 08:00)")
    return value.strip()


def _validate_positive_price(value: float) -> float:
    """El precio debe ser un número no negativo."""
    if value < 0:
        raise vol.Invalid("El precio no puede ser negativo")
    return value


# ---------------------------------------------------------------------------
# Config Flow principal
# ---------------------------------------------------------------------------

class PowerPricingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow para la integración Power Pricing."""

    VERSION = 1

    def __init__(self) -> None:
        self._tariff_type: str | None = None
        self._entry_name: str = "Power Pricing"
        # Acumulador de bloques TOU
        self._blocks: list[dict[str, Any]] = []
        self._num_blocks: int = 0
        self._current_block: int = 0
        # Acumulador para indexada
        self._indexed_base: str | None = None

    # -----------------------------------------------------------------------
    # STEP 1 — Nombre + tipo de tarifa
    # -----------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Paso inicial: nombre de la entrada y tipo de tarifa."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._entry_name = user_input[CONF_ENTRY_NAME].strip()
            self._tariff_type = user_input[CONF_TYPE]

            # Evitar entradas duplicadas con el mismo nombre
            await self.async_set_unique_id(self._entry_name.lower().replace(" ", "_"))
            self._abort_if_unique_id_configured()

            return await self._go_to_tariff_step()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTRY_NAME, default="Power Pricing"): str,
                    vol.Required(CONF_TYPE): vol.In(TARIFF_TYPE_LABELS),
                }
            ),
            errors=errors,
        )

    async def _go_to_tariff_step(self) -> FlowResult:
        """Redirige al step correspondiente según el tipo de tarifa."""
        if self._tariff_type == TARIFF_FIXED:
            return await self.async_step_fixed()
        if self._tariff_type == TARIFF_TOU:
            return await self.async_step_tou_blocks()
        if self._tariff_type == TARIFF_PVPC:
            return await self.async_step_pvpc()
        if self._tariff_type == TARIFF_INDEXED:
            return await self.async_step_indexed_base()
        return self.async_abort(reason="unknown_tariff")

    # -----------------------------------------------------------------------
    # TARIFA FIJA
    # -----------------------------------------------------------------------

    async def async_step_fixed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Precio fijo único (€/kWh)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                price = _validate_positive_price(float(user_input[CONF_PRICE]))
            except (vol.Invalid, ValueError):
                errors[CONF_PRICE] = "invalid_price"
            else:
                return self._create_entry(
                    {
                        CONF_TARIFF: {
                            CONF_TYPE: TARIFF_FIXED,
                            CONF_PARAMETERS: {CONF_PRICE: price},
                        }
                    }
                )

        return self.async_show_form(
            step_id="fixed",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE): vol.Coerce(float),
                }
            ),
            errors=errors,
            description_placeholders={"currency": "€/kWh"},
        )

    # -----------------------------------------------------------------------
    # TARIFA POR TRAMOS (TOU)
    # -----------------------------------------------------------------------

    async def async_step_tou_blocks(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Paso 1 de TOU: ¿cuántos tramos?"""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._blocks = []
            self._num_blocks = int(user_input[CONF_NUM_BLOCKS])
            self._current_block = 0
            return await self.async_step_tou_block()

        return self.async_show_form(
            step_id="tou_blocks",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NUM_BLOCKS, default=DEFAULT_NUM_BLOCKS): vol.All(
                        int, vol.Range(min=TOU_MIN_BLOCKS, max=TOU_MAX_BLOCKS)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_tou_block(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Paso 2-N de TOU: definir cada tramo horario."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validar formato de horas
            try:
                start = _validate_time(user_input[CONF_START])
                end = _validate_time(user_input[CONF_END])
            except vol.Invalid:
                errors["base"] = "invalid_time_format"
            else:
                # Evitar start == end (excepto 00:00–00:00 para "todo el día")
                if start == end and not (start == "00:00" and self._num_blocks == 1):
                    errors["base"] = "start_equals_end"
                else:
                    block: dict[str, Any] = {
                        CONF_START: start,
                        CONF_END: end,
                        CONF_PRICE: float(user_input[CONF_PRICE]),
                    }
                    if user_input.get(CONF_NAME):
                        block[CONF_NAME] = user_input[CONF_NAME].strip()

                    self._blocks.append(block)
                    self._current_block += 1

                    if self._current_block < self._num_blocks:
                        # Mostrar el formulario del siguiente bloque
                        return self.async_show_form(
                            step_id="tou_block",
                            data_schema=self._tou_block_schema(),
                            description_placeholders={
                                "current": str(self._current_block + 1),
                                "total": str(self._num_blocks),
                            },
                        )

                    # Todos los bloques completados
                    return self._create_entry(
                        {
                            CONF_TARIFF: {
                                CONF_TYPE: TARIFF_TOU,
                                CONF_PARAMETERS: {CONF_BLOCKS: self._blocks},
                            }
                        }
                    )

        return self.async_show_form(
            step_id="tou_block",
            data_schema=self._tou_block_schema(),
            errors=errors,
            description_placeholders={
                "current": str(self._current_block + 1),
                "total": str(self._num_blocks),
            },
        )

    @staticmethod
    def _tou_block_schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(CONF_NAME): str,
                vol.Required(CONF_START): str,   # validado manualmente
                vol.Required(CONF_END): str,
                vol.Required(CONF_PRICE): vol.Coerce(float),
            }
        )

    # -----------------------------------------------------------------------
    # PVPC
    # -----------------------------------------------------------------------

    async def async_step_pvpc(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configuración PVPC: solo zona geográfica. Sin token necesario."""
        if user_input is not None:
            return self._create_entry(
                {
                    CONF_GEO_ZONE: user_input[CONF_GEO_ZONE],
                    CONF_TARIFF: {
                        CONF_TYPE: TARIFF_PVPC,
                        CONF_PARAMETERS: {},
                    },
                }
            )

        return self.async_show_form(
            step_id="pvpc",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GEO_ZONE, default=GEO_ZONE_PCB): vol.In(
                        GEO_ZONE_LABELS
                    ),
                }
            ),
        )

    # -----------------------------------------------------------------------
    # INDEXADA
    # -----------------------------------------------------------------------

    async def async_step_indexed_base(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Indexada paso 1: precio base de referencia."""
        if user_input is not None:
            self._indexed_base = user_input[CONF_BASE]
            return await self.async_step_indexed_adjustments()

        return self.async_show_form(
            step_id="indexed_base",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE): vol.In(INDEXED_BASE_LABELS),
                }
            ),
        )

    async def async_step_indexed_adjustments(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Indexada paso 2: zona geográfica y ajustes de precio."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                multiplier = float(user_input[CONF_MULTIPLIER])
                markup = float(user_input[CONF_FIXED_MARKUP])
                if multiplier <= 0:
                    errors[CONF_MULTIPLIER] = "multiplier_not_positive"
            except ValueError:
                errors["base"] = "invalid_number"

            if not errors:
                return self._create_entry(
                    {
                        CONF_GEO_ZONE: user_input[CONF_GEO_ZONE],
                        CONF_TARIFF: {
                            CONF_TYPE: TARIFF_INDEXED,
                            CONF_PARAMETERS: {
                                CONF_BASE: self._indexed_base,
                                CONF_MULTIPLIER: multiplier,
                                CONF_FIXED_MARKUP: markup,
                            },
                        },
                    }
                )

        return self.async_show_form(
            step_id="indexed_adjustments",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GEO_ZONE, default=GEO_ZONE_PCB): vol.In(
                        GEO_ZONE_LABELS
                    ),
                    vol.Required(CONF_MULTIPLIER, default=DEFAULT_MULTIPLIER): vol.Coerce(float),
                    vol.Required(CONF_FIXED_MARKUP, default=DEFAULT_FIXED_MARKUP): vol.Coerce(float),
                }
            ),
            errors=errors,
            description_placeholders={
                "formula": "precio_final = precio_base × multiplicador + margen_fijo",
            },
        )

    # -----------------------------------------------------------------------
    # CREAR ENTRADA
    # -----------------------------------------------------------------------

    def _create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Crea la config entry con el nombre elegido por el usuario."""
        return self.async_create_entry(
            title=self._entry_name,
            data=data,
        )
