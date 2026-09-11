"""
Copyright (c) 2026 Kevin Yeh

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

from openpilot.selfdrive.ui.onroad.alert_renderer import ALERT_COLORS, AlertStatus
from openpilot.selfdrive.ui.onroad.hud_renderer import COLORS
from openpilot.selfdrive.ui.sunnypilot.onroad.performance_constants import TRANS_HOT_TEMP_C, TRANS_OVER_TEMP_C, TRANS_WARM_TEMP_C

# Reuse the alert banner's palette: its "normal" background is already a vetted near-opaque
# near-black tile, and userPrompt/critical are this app's canonical warn/crit colors.
TILE_BG_COLOR = ALERT_COLORS[AlertStatus.normal]

# Semantic gauge, ascending: cold -> normal -> hot -> overheat. No existing onroad blue to reuse,
# so cold stays a custom color. Dict order doubles as display order (e.g. the tile row).
REGION_COLORS = {
  "COLD": rl.Color(96, 165, 250, 255),
  "NORMAL": COLORS.WHITE_TRANSLUCENT,
  "HOT": ALERT_COLORS[AlertStatus.userPrompt],
  "OVERHEAT": ALERT_COLORS[AlertStatus.critical],
}
REGION_ORDER = tuple(REGION_COLORS)


def get_region_for_temp(temp: float) -> str:
  if temp >= TRANS_OVER_TEMP_C:
    return "OVERHEAT"
  if temp >= TRANS_HOT_TEMP_C:
    return "HOT"
  if temp < TRANS_WARM_TEMP_C:
    return "COLD"
  return "NORMAL"


def get_color_for_temp(temp: float) -> rl.Color:
  return REGION_COLORS[get_region_for_temp(temp)]
