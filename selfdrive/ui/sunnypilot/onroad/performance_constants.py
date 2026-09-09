"""
Copyright (c) 2026 Kevin Yeh

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

from openpilot.selfdrive.ui.onroad.alert_renderer import ALERT_COLORS, AlertStatus
from openpilot.selfdrive.ui.onroad.hud_renderer import COLORS

TRANS_COLD_TEMP_C = 79.0
TRANS_WARN_TEMP_C = 120.0
TRANS_CRIT_TEMP_C = 135.0
THRESHOLDS = (TRANS_COLD_TEMP_C, TRANS_WARN_TEMP_C, TRANS_CRIT_TEMP_C)

HISTORY_WINDOW_S = 1800  # 30 minutes, in-memory only (resets on restart)
HISTORY_SAMPLE_INTERVAL_S = 1.0
HISTORY_MAXLEN = int(HISTORY_WINDOW_S / HISTORY_SAMPLE_INTERVAL_S)

# PerformanceRenderer: the small always-on onroad tile.
LEFT_MARGIN = 60
TILE_PADDING = 16
TILE_ROUNDNESS = 0.2

# Widest realistic digit strings, so the tile's width is reserved up front and never shifts as the
# live value's digit count changes (e.g. "50" vs "122" vs "-5"). "0" measures wider than every
# other digit in this font, so it - not "9" - is the correct worst-case filler digit.
VALUE_WIDTH_REFERENCES = ("-00", "000")

# PerformanceGraph: the tap-to-view full-screen history overlay.
GRAPH_MARGIN_X = 160
GRAPH_MARGIN_TOP = 160
GRAPH_MARGIN_BOTTOM = 220
LINE_THICKNESS = 7
GRID_COLOR = rl.Color(255, 255, 255, 60)
LABEL_FONT_SIZE = 36

REGION_TILE_GAP = 20
REGION_TILE_HEIGHT = 130
REGION_TILE_LABEL_FONT_SIZE = 28
REGION_TILE_VALUE_FONT_SIZE = 44
TIME_TICK_INTERVAL_S = 600  # 10 minutes

# Reuse the alert banner's palette: its "normal" background is already a vetted near-opaque
# near-black tile, and userPrompt/critical are this app's canonical warn/crit colors.
TILE_BG_COLOR = ALERT_COLORS[AlertStatus.normal]

# Semantic gauge, ascending: cold -> normal -> warn -> critical. No existing onroad blue to reuse,
# so cold stays a custom color. Dict order doubles as display order (e.g. the tile row).
REGION_COLORS = {
  "COLD": rl.Color(96, 165, 250, 255),
  "NORMAL": COLORS.WHITE_TRANSLUCENT,
  "WARN": ALERT_COLORS[AlertStatus.userPrompt],
  "CRITICAL": ALERT_COLORS[AlertStatus.critical],
}
REGION_ORDER = tuple(REGION_COLORS)


def get_region_for_temp(temp: float) -> str:
  if temp >= TRANS_CRIT_TEMP_C:
    return "CRITICAL"
  if temp >= TRANS_WARN_TEMP_C:
    return "WARN"
  if temp < TRANS_COLD_TEMP_C:
    return "COLD"
  return "NORMAL"


def get_color_for_temp(temp: float) -> rl.Color:
  return REGION_COLORS[get_region_for_temp(temp)]
