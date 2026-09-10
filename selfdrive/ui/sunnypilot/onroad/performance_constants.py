"""
Copyright (c) 2026 Kevin Yeh

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

TRANS_ROOM_TEMP_C = 20.0
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
MINMAX_LINE_COLOR = rl.Color(255, 255, 255, 130)

REGION_TILE_GAP = 20
REGION_TILE_HEIGHT = 130
REGION_TILE_LABEL_FONT_SIZE = 28
REGION_TILE_VALUE_FONT_SIZE = 44
# Candidate tick spacings; _pick_tick_interval() picks the smallest one that keeps the tick count
# at or below TIME_TICK_MAX_COUNT for however much history is currently on screen, so a short
# session (e.g. 90s in) still gets several labeled ticks instead of waiting for the first 10m one.
TIME_TICK_INTERVALS_S = (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800)
TIME_TICK_MAX_COUNT = 6
