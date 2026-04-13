"""Coordinator para Power Pricing.

Fuente de datos PVPC/Indexada: api.preciodelaluz.org (sin token, datos de REE).
Endpoint principal: GET /v1/prices/all?zone=PCB|CYM

Responsabilidades:
  - PVPC / Indexada : descarga los 24 precios del día y calcula estadísticas.
  - Fija / TOU      : calcula el precio localmente sin llamadas externas.
  - Expone current_price, today_prices, tomorrow_prices y price_stats.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BASE,
    CONF_BLOCKS,
    CONF_END,
    CONF_FIXED_MARKUP,
    CONF_GEO_ZONE,
    CONF_MULTIPLIER,
    CONF_PARAMETERS,
    CONF_PRICE,
    CONF_START,
    CONF_TARIFF,
    CONF_TYPE,
    DOMAIN,
    GEO_ZONE_PCB,
    TARIFF_FIXED,
    TARIFF_INDEXED,
    TARIFF_PVPC,
    TARIFF_TOU,
)

_LOGGER = logging.getLogger(__name__)

_API_BASE = "https://api.preciodelaluz.org/v1/prices"
_API_ALL  = _API_BASE + "/all"
_TIMEZONE = ZoneInfo("Europe/Madrid")

# Actualizamos cada hora. REE publica precios del día siguiente ~20:15h.
UPDATE_INTERVAL = timedelta(minutes=60)


class PowerPricingCoordinator(DataUpdateCoordinator):
    """Coordinator central de Power Pricing."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self._tariff_cfg: dict[str, Any] = entry.data.get(CONF_TARIFF, {})
        self._tariff_type: str = self._tariff_cfg.get(CONF_TYPE, TARIFF_FIXED)
        self._params: dict[str, Any] = self._tariff_cfg.get(CONF_PARAMETERS, {})
        self._zone: str = entry.data.get(CONF_GEO_ZONE, GEO_ZONE_PCB)

        # Caché diaria: evita llamadas redundantes dentro del mismo día
        self._cache: dict[str, dict[int, float]] = {}  # {"YYYY-MM-DD_zone": {h: €/kWh}}

        # ── Datos públicos para los sensores ─────────────────────────────
        self.current_price: float | None = None
        self.today_prices: dict[int, float] = {}
        self.tomorrow_prices: dict[int, float] = {}
        self.price_stats: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Punto de entrada del coordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        if self._tariff_type == TARIFF_FIXED:
            return self._update_fixed()
        if self._tariff_type == TARIFF_TOU:
            return self._update_tou()
        if self._tariff_type in (TARIFF_PVPC, TARIFF_INDEXED):
            return await self._update_from_api()
        raise UpdateFailed(f"Tipo de tarifa desconocido: {self._tariff_type}")

    # ------------------------------------------------------------------
    # TARIFA FIJA
    # ------------------------------------------------------------------

    def _update_fixed(self) -> dict[str, Any]:
        price = float(self._params.get(CONF_PRICE, 0.0))
        self.current_price = price
        self.today_prices = {h: price for h in range(24)}
        self.tomorrow_prices = self.today_prices.copy()
        self.price_stats = self._compute_stats(self.today_prices)
        return {"current_price": price}

    # ------------------------------------------------------------------
    # TARIFA POR TRAMOS (TOU)
    # ------------------------------------------------------------------

    def _update_tou(self) -> dict[str, Any]:
        blocks: list[dict[str, Any]] = self._params.get(CONF_BLOCKS, [])
        now_local = datetime.now(tz=_TIMEZONE)
        self.today_prices = {h: self._price_for_hour_tou(h, blocks) for h in range(24)}
        self.tomorrow_prices = self.today_prices.copy()
        self.current_price = self._price_for_hour_tou(now_local.hour, blocks)
        self.price_stats = self._compute_stats(self.today_prices)
        return {"current_price": self.current_price}

    @staticmethod
    def _price_for_hour_tou(hour: int, blocks: list[dict]) -> float | None:
        """Precio €/kWh para una hora según bloques TOU. Soporta tramos nocturnos."""
        for block in blocks:
            sh, sm = map(int, block[CONF_START].split(":"))
            eh, em = map(int, block[CONF_END].split(":"))
            s_min = sh * 60 + sm
            e_min = eh * 60 + em
            c_min = hour * 60

            if s_min < e_min:
                if s_min <= c_min < e_min:
                    return float(block[CONF_PRICE])
            else:                                   # Tramo que cruza medianoche
                if c_min >= s_min or c_min < e_min:
                    return float(block[CONF_PRICE])

        _LOGGER.warning("Hora %d no cubierta por ningún tramo TOU.", hour)
        return None

    # ------------------------------------------------------------------
    # PVPC / INDEXADA — api.preciodelaluz.org (sin token)
    # ------------------------------------------------------------------

    async def _update_from_api(self) -> dict[str, Any]:
        now_local = datetime.now(tz=_TIMEZONE)
        today_raw    = await self._fetch_day(now_local.date())
        tomorrow_raw = await self._fetch_day((now_local + timedelta(days=1)).date())

        if not today_raw:
            raise UpdateFailed(
                "No se obtuvieron precios de hoy desde api.preciodelaluz.org. "
                "Comprueba la conexión a internet."
            )

        self.today_prices    = today_raw
        self.tomorrow_prices = tomorrow_raw or {}

        # Ajustes para tarifa indexada: precio = pvpc × mult + margen
        if self._tariff_type == TARIFF_INDEXED:
            mult   = float(self._params.get(CONF_MULTIPLIER, 1.0))
            markup = float(self._params.get(CONF_FIXED_MARKUP, 0.0))
            self.today_prices = {
                h: round(p * mult + markup, 6) for h, p in self.today_prices.items()
            }
            self.tomorrow_prices = {
                h: round(p * mult + markup, 6) for h, p in self.tomorrow_prices.items()
            }

        self.current_price = self.today_prices.get(now_local.hour)
        self.price_stats   = self._compute_stats(self.today_prices, self.tomorrow_prices)

        _LOGGER.debug(
            "[%s] h=%d → %.5f €/kWh | min=%.5f @ %s | max=%.5f @ %s",
            self.entry.title,
            now_local.hour,
            self.current_price or 0,
            self.price_stats.get("today_min", 0),
            self.price_stats.get("today_min_at", "?"),
            self.price_stats.get("today_max", 0),
            self.price_stats.get("today_max_at", "?"),
        )

        return {
            "current_price": self.current_price,
            "today":         self.today_prices,
            "tomorrow":      self.tomorrow_prices,
            "stats":         self.price_stats,
        }

    async def _fetch_day(self, day: Any) -> dict[int, float] | None:
        """Descarga precios de un día desde preciodelaluz.org.

        Devuelve {hora_int: precio_€/kWh} o None si no hay datos todavía.
        La API ya devuelve los valores en €/kWh (no en €/MWh).
        """
        date_str  = day.strftime("%Y-%m-%d")
        cache_key = f"{date_str}_{self._zone}"

        if cache_key in self._cache:
            _LOGGER.debug("Cache hit: %s", cache_key)
            return self._cache[cache_key]

        url = f"{_API_ALL}?zone={self._zone}&date={date_str}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status == 404:
                        # Datos de mañana aún no publicados (normal antes de las ~20:15)
                        _LOGGER.debug("Precios de %s aún no disponibles.", date_str)
                        return None
                    if resp.status != 200:
                        _LOGGER.warning(
                            "preciodelaluz.org respondió HTTP %d para %s",
                            resp.status, date_str,
                        )
                        return None
                    raw: dict = await resp.json()

        except aiohttp.ClientError as err:
            raise UpdateFailed(
                f"Error de red al contactar preciodelaluz.org: {err}"
            ) from err

        # La respuesta es {"00": {"price": 0.123, "is-cheap": true, ...}, "01": ...}
        prices: dict[int, float] = {}
        for key, entry in raw.items():
            try:
                prices[int(key)] = float(entry["price"])
            except (ValueError, KeyError, TypeError) as err:
                _LOGGER.warning("Entrada ignorada '%s': %s", key, err)

        if prices:
            self._cache[cache_key] = prices
            self._purge_old_cache(day)

        return prices or None

    def _purge_old_cache(self, ref_day: Any) -> None:
        cutoff = (ref_day - timedelta(days=2)).strftime("%Y-%m-%d")
        for k in [k for k in self._cache if k[:10] < cutoff]:
            del self._cache[k]
            _LOGGER.debug("Cache purgada: %s", k)

    # ------------------------------------------------------------------
    # Estadísticas — calculadas localmente sobre los precios del día
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_stats(
        today: dict[int, float],
        tomorrow: dict[int, float] | None = None,
    ) -> dict[str, Any]:
        """Calcula min, max, media, hora más barata/cara y horas baratas."""
        if not today:
            return {}

        vals     = list(today.values())
        min_p    = min(vals)
        max_p    = max(vals)
        mean_p   = sum(vals) / len(vals)
        min_h    = min(today, key=today.get)
        max_h    = max(today, key=today.get)

        # Horas por debajo de la media, ordenadas de más barata a más cara
        cheap_hours: list[int] = sorted(
            [h for h, p in today.items() if p < mean_p],
            key=lambda h: today[h],
        )

        stats: dict[str, Any] = {
            # Precio actual del día
            "today_min":         round(min_p, 5),
            "today_max":         round(max_p, 5),
            "today_mean":        round(mean_p, 5),
            "today_min_at":      f"{min_h:02d}:00",
            "today_max_at":      f"{max_h:02d}:00",
            "today_cheap_hours": cheap_hours,
            # Serie completa de hoy (para gráficas en el frontend de HA)
            "today_prices": {
                f"{h:02d}:00": round(p, 5) for h, p in sorted(today.items())
            },
        }

        if tomorrow:
            t_vals  = list(tomorrow.values())
            t_min   = min(t_vals)
            t_max   = max(t_vals)
            t_mean  = sum(t_vals) / len(t_vals)
            t_min_h = min(tomorrow, key=tomorrow.get)
            t_max_h = max(tomorrow, key=tomorrow.get)
            stats.update(
                {
                    "tomorrow_min":    round(t_min, 5),
                    "tomorrow_max":    round(t_max, 5),
                    "tomorrow_mean":   round(t_mean, 5),
                    "tomorrow_min_at": f"{t_min_h:02d}:00",
                    "tomorrow_max_at": f"{t_max_h:02d}:00",
                    "tomorrow_prices": {
                        f"{h:02d}:00": round(p, 5)
                        for h, p in sorted(tomorrow.items())
                    },
                }
            )

        return stats
