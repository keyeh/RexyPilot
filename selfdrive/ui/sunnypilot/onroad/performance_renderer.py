"""
Copyright (c) 2026 Kevin Yeh

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import math
import pyray as rl

from openpilot.selfdrive.ui.onroad.alert_renderer import ALERT_COLORS, AlertStatus
from openpilot.selfdrive.ui.onroad.hud_renderer import FONT_SIZES, COLORS
from openpilot.selfdrive.ui.sunnypilot.onroad.performance_constants import TRANS_COLD_TEMP_C, TRANS_WARN_TEMP_C, TRANS_CRIT_TEMP_C
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

LEFT_MARGIN = 60
LABEL_GAP = 10
TILE_PADDING_X = 24
TILE_PADDING_Y = 16
TILE_ROUNDNESS = 0.2

# Reuse the alert banner's palette: its "normal" background is already a vetted near-opaque
# near-black tile, and userPrompt/critical are this app's canonical warn/crit colors.
TILE_BG_COLOR = ALERT_COLORS[AlertStatus.normal]

# Semantic gauge: cold -> normal -> warn -> crit, full opacity so severity reads at a glance without
# reading the digits. No existing onroad blue to reuse, so cold stays a custom color.
COLOR_COLD = rl.Color(96, 165, 250, 255)
COLOR_NORMAL = COLORS.WHITE_TRANSLUCENT
COLOR_WARN = ALERT_COLORS[AlertStatus.userPrompt]
COLOR_CRIT = ALERT_COLORS[AlertStatus.critical]


class PerformanceRenderer(Widget):
  def __init__(self):
    super().__init__()
    self.trans_oil_temp = float('nan')
    self.font = gui_app.font(FontWeight.BOLD)
    self.font_label = gui_app.font(FontWeight.MEDIUM)

  def update(self):
    sm = ui_state.sm
    if sm.recv_frame["carStateSP"] < ui_state.started_frame:
      return

    self.trans_oil_temp = sm["carStateSP"].transOilTemp

  def _render(self, rect: rl.Rectangle) -> None:
    if math.isnan(self.trans_oil_temp):
      return

    # TODO: temporarily hardcoded to Celsius for testing, revert to ui_state.is_metric
    is_metric = True
    value = self.trans_oil_temp if is_metric else self.trans_oil_temp * 9 / 5 + 32
    text = f"{value:.0f}{'C' if is_metric else 'F'}"

    color = COLOR_NORMAL
    if self.trans_oil_temp >= TRANS_CRIT_TEMP_C:
      color = COLOR_CRIT
    elif self.trans_oil_temp >= TRANS_WARN_TEMP_C:
      color = COLOR_WARN
    elif self.trans_oil_temp < TRANS_COLD_TEMP_C:
      color = COLOR_COLD

    label_text = tr("TRANS TEMP")
    label_size = measure_text_cached(self.font_label, label_text, FONT_SIZES.speed_unit)
    text_size = measure_text_cached(self.font, text, FONT_SIZES.current_speed)

    block_width = max(label_size.x, text_size.x)
    block_height = label_size.y + LABEL_GAP + text_size.y
    block_y = rect.y + rect.height / 2 - block_height / 2

    tile_rect = rl.Rectangle(
      rect.x + LEFT_MARGIN - TILE_PADDING_X,
      block_y - TILE_PADDING_Y,
      block_width + TILE_PADDING_X * 2,
      block_height + TILE_PADDING_Y * 2,
    )
    rl.draw_rectangle_rounded(tile_rect, TILE_ROUNDNESS, 10, TILE_BG_COLOR)
    rl.draw_rectangle_rounded_lines_ex(tile_rect, TILE_ROUNDNESS, 10, 3, COLORS.BORDER_TRANSLUCENT)

    label_origin = rl.Vector2(rect.x + LEFT_MARGIN + (block_width - label_size.x) / 2, block_y)
    rl.draw_text_ex(self.font_label, label_text, label_origin, FONT_SIZES.speed_unit, 0, COLORS.GREY)

    value_origin = rl.Vector2(rect.x + LEFT_MARGIN + (block_width - text_size.x) / 2, block_y + label_size.y + LABEL_GAP)
    rl.draw_text_ex(self.font, text, value_origin, FONT_SIZES.current_speed, 0, color)
