"""
Copyright (c) 2026 Kevin Yeh

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

# Temperature thresholds (transmission oil temp, Celsius)
TRANS_ROOM_TEMP_C = 25.0  # gauge/chart domain floor, not a region boundary
TRANS_COLD_TEMP_C = 79.0
TRANS_WARN_TEMP_C = 120.0
TRANS_CRIT_TEMP_C = 135.0
THRESHOLDS = (TRANS_COLD_TEMP_C, TRANS_WARN_TEMP_C, TRANS_CRIT_TEMP_C)  # ascending order - zipped with region labels elsewhere

GAUGE_TICK_VALUES = (TRANS_ROOM_TEMP_C, *THRESHOLDS)  # temps shown as ticks on the gauge

# History buffer
HISTORY_WINDOW_S = 1800  # 30 minutes, in-memory only (resets on restart)
HISTORY_SAMPLE_INTERVAL_S = 1.0
HISTORY_MAXLEN = int(HISTORY_WINDOW_S / HISTORY_SAMPLE_INTERVAL_S)

# PerformanceRenderer: the small always-on onroad tile
TILE_LEFT_MARGIN = 60
TILE_PADDING = 16
ROUNDNESS = 0.2  # shared by the onroad tile, the gauge bar, and the region tiles
BORDER_THICKNESS = 8  # shared by the onroad tile and the gauge bar, so their outlines match

# PerformanceGraph: the tap-to-view full-screen history overlay
CONTENT_MARGIN_X = 40  # left/right margin of the whole content column
CONTENT_MARGIN_Y = 40  # top/bottom margin of the whole content column; the plot between them sizes dynamically to fill what's left
HEADER_GAP = 40  # header bottom -> plot top (separate from CONTENT_MARGIN_Y, which covers screen edge -> header)
CHART_LINE_THICKNESS = 7  # gridlines/minmax line use a hardcoded 2px instead
GRID_COLOR = rl.Color(255, 255, 255, 60)
LABEL_FONT_SIZE = 36  # shared by every small label in the overlay (ticks, gridlines, axis, etc.)
MINMAX_LINE_COLOR = rl.Color(255, 255, 255, 130)
THRESHOLD_LABEL_GAP = 20  # chart is narrowed to reserve this + the widest COLD/WARN/CRIT label, so the label can't overlap the gridline

# Left column: gauge bar + readout, left-aligned at CONTENT_MARGIN_X. The bar's width is derived at render time to match the readout's width, so there's no dead space before the chart.
GAUGE_COLUMN_GAP = 15  # single gap reused bar->labels and labels->chart, so spacing stays equal
GAUGE_READOUT_GAP = 30  # minimum gap below the gauge bar; the readout is bottom-anchored, so the actual gap grows if the region tiles need more room (see _render)
READOUT_UNIT_GAP = 8

# Widest realistic digit strings, so width is reserved up front and never shifts as the live value's
# digit count changes. "0" is the widest digit in this font (right filler for non-leading positions);
# "4" is the widest of 1-9 (a real number never has a leading zero).
VALUE_WIDTH_REFERENCES = ("-40", "400")

# Region-duration tiles below the chart
REGION_TILE_GAP = 20
REGION_TILE_HEIGHT = 130
REGION_TILE_LABEL_FONT_SIZE = 28
REGION_TILE_VALUE_FONT_SIZE = 44
REGION_TILES_MARGIN_TOP = 80  # minimum gap above the tiles; they're bottom-anchored, so the actual gap grows if the readout needs more room (see _render)

# Rate-of-change stat, leftmost in the region-tile row (see _draw_rate_stat)
RATE_WINDOW_S = 5.0  # smooths over the last few seconds so one noisy sample doesn't swing the reading
RATE_STEADY_THRESHOLD_C_S = 0.1  # magnitude below this reads as "steady" rather than rising/falling

# Chart time axis
TIME_TICK_INTERVALS_S = (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800)  # candidates; _draw_time_labels() picks the smallest keeping tick count <= TIME_TICK_MAX_COUNT
TIME_TICK_MAX_COUNT = 6
