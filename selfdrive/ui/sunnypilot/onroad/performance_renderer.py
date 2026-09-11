"""
Copyright (c) 2026 Kevin Yeh

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import math
from collections import deque
from collections.abc import Iterable
from typing import NamedTuple

import pyray as rl

from openpilot.selfdrive.ui.onroad.hud_renderer import FONT_SIZES, COLORS
from openpilot.selfdrive.ui.sunnypilot.onroad.performance_colors import (
  REGION_COLORS,
  REGION_ORDER,
  TILE_BG_COLOR,
  get_color_for_temp,
  get_region_for_temp,
)
from openpilot.selfdrive.ui.sunnypilot.onroad.performance_constants import (
  BORDER_THICKNESS,
  CHART_LINE_THICKNESS,
  CONTENT_MARGIN_X,
  CONTENT_MARGIN_Y,
  GAUGE_COLUMN_GAP,
  GAUGE_READOUT_GAP,
  GAUGE_TICK_VALUES,
  GRID_COLOR,
  HEADER_GAP,
  HISTORY_MAXLEN,
  HISTORY_SAMPLE_INTERVAL_S,
  LABEL_FONT_SIZE,
  MINMAX_LINE_COLOR,
  RATE_STEADY_THRESHOLD_C_S,
  RATE_WINDOW_S,
  READOUT_UNIT_GAP,
  REGION_TILE_GAP,
  REGION_TILE_HEIGHT,
  REGION_TILE_LABEL_FONT_SIZE,
  REGION_TILE_VALUE_FONT_SIZE,
  REGION_TILES_MARGIN_TOP,
  ROUNDNESS,
  THRESHOLDS,
  THRESHOLD_LABELS,
  THRESHOLD_LABEL_GAP,
  TILE_LEFT_MARGIN,
  TILE_PADDING,
  TIME_TICK_INTERVALS_S,
  TIME_TICK_MAX_COUNT,
  TRANS_OVER_TEMP_C,
  TRANS_ROOM_TEMP_C,
  VALUE_WIDTH_REFERENCES,
)
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app, FontWeight, FONT_SCALE
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget


def read_and_sample_trans_oil_temp(history: deque[tuple[float, float]]) -> float:
  """Reads the live transOilTemp and appends a history sample if due.

  Must be called every frame by whichever widget is actually rendering, since only the top-of-nav-stack widget renders.
  """
  sm = ui_state.sm
  if sm.recv_frame["carStateSP"] < ui_state.started_frame:
    return float('nan')
  temp = sm["carStateSP"].transOilTemp
  if not math.isnan(temp):
    now = rl.get_time()
    if not history or now - history[-1][0] >= HISTORY_SAMPLE_INTERVAL_S:
      history.append((now, temp))
  return temp


def _is_metric() -> bool:
  return True  # TODO: temporarily hardcoded to Celsius for testing
  # return ui_state.is_metric


def _split_at_thresholds(t0: float, v0: float, t1: float, v1: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
  """Split a (t0,v0)->(t1,v1) segment at every threshold it crosses, so each sub-segment maps to one region."""
  crossings = []
  for threshold in THRESHOLDS:
    lo, hi = min(v0, v1), max(v0, v1)
    if lo < threshold < hi:
      frac = (threshold - v0) / (v1 - v0)
      crossings.append((t0 + frac * (t1 - t0), threshold))
  crossings.sort()

  points = [(t0, v0), *crossings, (t1, v1)]
  return list(zip(points, points[1:]))


def _format_duration(seconds: float) -> str:
  total_seconds = int(seconds)
  hours, remainder = divmod(total_seconds, 3600)
  minutes, secs = divmod(remainder, 60)
  if hours:
    return f"{hours}h {minutes}m"
  if minutes:
    return f"{minutes}m {secs}s"
  return f"{secs}s"


def _compute_rate(samples: list[tuple[float, float]]) -> float | None:
  """°C/s over the last RATE_WINDOW_S of history, or the whole buffer if it's shorter than that."""
  if len(samples) < 2:
    return None
  latest_t, latest_v = samples[-1]
  window_start = latest_t - RATE_WINDOW_S
  ref_t, ref_v = next(((t, v) for t, v in samples if t >= window_start), samples[0])
  dt = latest_t - ref_t
  if dt <= 0:
    return None
  return (latest_v - ref_v) / dt


def _format_tick_offset(offset_s: int) -> str:
  """Unlike _format_duration, must not floor a non-round-minute offset (e.g. 75s) to "-1m", or distinct ticks would collide."""
  if offset_s < 60:
    return f"-{offset_s}s"
  minutes, secs = divmod(offset_s, 60)
  if secs:
    return f"-{minutes}m{secs:02d}s"
  return f"-{minutes}m"


def _convert_temp(value_c: float, is_metric: bool) -> tuple[float, str]:
  value = value_c if is_metric else value_c * 9 / 5 + 32
  unit = "C" if is_metric else "F"
  return value, unit


class _TextItem(NamedTuple):
  font: rl.Font
  text: str
  size: rl.Vector2
  font_size: int
  color: rl.Color


def _max_text_width(font: rl.Font, texts: Iterable[str], font_size: int) -> float:
  return max(measure_text_cached(font, text, font_size).x for text in texts)


def _max_font_size_to_fit(font: rl.Font, text: str, max_width: float, max_height: float, reference_size: int = 100) -> int:
  """Largest font size for `text` that still fits within max_width/max_height, since text size scales linearly with font size."""
  reference = measure_text_cached(font, text, reference_size)
  scale = min(max_width / reference.x, max_height / reference.y)
  return int(reference_size * scale)


def _ink_top_offset(font: rl.Font, text: str, font_size: int) -> float:
  """Vertical distance from a draw_text_ex origin down to the text's topmost ink pixel.

  measure_text_cached/draw_text_ex size text boxes to font_size (line-height), not glyph ink extent,
  so two differently-sized strings drawn at the same origin.y do NOT have their ink tops line up.
  Glyphs are authored at font.baseSize and scaled to the requested size when drawn, so we replicate
  that scaling here using the font's real per-glyph offsetY to find the true ink top.
  """
  scale = font_size * FONT_SCALE / font.baseSize
  offsets = [font.glyphs[rl.get_glyph_index(font, ord(ch))].offsetY for ch in text if not ch.isspace()]
  return min(offsets, default=0) * scale


def _text_item(font: rl.Font, text: str, font_size: int, color: rl.Color) -> _TextItem:
  return _TextItem(font, text, measure_text_cached(font, text, font_size), font_size, color)


def _draw_centered_stack(items: list[_TextItem], center_x: float, top_y: float, gap: float = 0) -> None:
  """Draw texts stacked vertically, each horizontally centered on center_x."""
  y = top_y
  for item in items:
    rl.draw_text_ex(item.font, item.text, rl.Vector2(center_x - item.size.x / 2, y), item.font_size, 0, item.color)
    y += item.size.y + gap


def _draw_rounded_tile(rect: rl.Rectangle, bg_color: rl.Color, border_color: rl.Color, border_thickness: float = BORDER_THICKNESS) -> None:
  rl.draw_rectangle_rounded(rect, ROUNDNESS, 10, bg_color)
  rl.draw_rectangle_rounded_lines_ex(rect, ROUNDNESS, 10, border_thickness, border_color)


class PerformanceRenderer(Widget):
  def __init__(self):
    super().__init__()
    self.trans_oil_temp = float('nan')
    self.history: deque[tuple[float, float]] = deque(maxlen=HISTORY_MAXLEN)
    self._tile_rect = rl.Rectangle(0, 0, 0, 0)
    self.font = gui_app.font(FontWeight.BOLD)
    self.font_label = gui_app.font(FontWeight.MEDIUM)
    self._graph = PerformanceGraph(self.history)
    self.set_click_callback(lambda: gui_app.push_widget(self._graph))

  @property
  def _hit_rect(self) -> rl.Rectangle:
    return self._tile_rect  # restrict taps to the visible tile, not the full HUD rect

  def update(self):
    self.trans_oil_temp = read_and_sample_trans_oil_temp(self.history)

  def _render(self, rect: rl.Rectangle) -> None:
    if math.isnan(self.trans_oil_temp):
      self._tile_rect = rl.Rectangle(0, 0, 0, 0)
      return

    value, unit = _convert_temp(self.trans_oil_temp, _is_metric())
    color = get_color_for_temp(self.trans_oil_temp)

    items = [
      _text_item(self.font_label, tr("TRANS"), FONT_SIZES.speed_unit, COLORS.GREY),
      _text_item(self.font, f"{value:.0f}", FONT_SIZES.current_speed, color),
      _text_item(self.font_label, f"°{unit}", FONT_SIZES.speed_unit, COLORS.GREY),
    ]
    value_width = _max_text_width(self.font, VALUE_WIDTH_REFERENCES, FONT_SIZES.current_speed)

    block_width = max(value_width, *(item.size.x for item in items))
    block_height = sum(item.size.y for item in items)
    block_y = rect.y + rect.height / 2 - block_height / 2

    tile_rect = rl.Rectangle(
      rect.x + TILE_LEFT_MARGIN - TILE_PADDING,
      block_y - TILE_PADDING,
      block_width + TILE_PADDING * 2,
      block_height + TILE_PADDING * 2,
    )
    _draw_rounded_tile(tile_rect, TILE_BG_COLOR, color)
    self._tile_rect = tile_rect

    _draw_centered_stack(items, rect.x + TILE_LEFT_MARGIN + block_width / 2, block_y)


class PerformanceGraph(Widget):
  """Full-screen overlay plotting transOilTemp history. Tap anywhere to dismiss."""

  def __init__(self, history: deque[tuple[float, float]]):
    super().__init__()
    self._history = history
    self._font_title = gui_app.font(FontWeight.BOLD)
    self._font_label = gui_app.font(FontWeight.MEDIUM)

  def _handle_mouse_release(self, mouse_pos) -> None:
    super()._handle_mouse_release(mouse_pos)
    gui_app.pop_widget()

  def show_event(self) -> None:
    super().show_event()
    ui_state.performance_graph_active = True

  def hide_event(self) -> None:
    super().hide_event()
    ui_state.performance_graph_active = False

  def _render(self, rect: rl.Rectangle) -> None:
    rl.draw_rectangle_rec(rect, TILE_BG_COLOR)

    is_metric = _is_metric()

    live_temp = read_and_sample_trans_oil_temp(self._history)
    samples = list(self._history)

    content_x = rect.x + CONTENT_MARGIN_X
    header_bottom = self._draw_header(rect, content_x)

    # Bottom-anchored elements (see _draw_readout/_draw_region_tiles): whichever is taller sets the plot's bottom edge; the other just gets extra room above it.
    plot_y = header_bottom + HEADER_GAP
    value_text_height = measure_text_cached(self._font_title, "0", FONT_SIZES.current_speed).y
    readout_content_height = GAUGE_READOUT_GAP + value_text_height
    chart_content_height = REGION_TILES_MARGIN_TOP + REGION_TILE_HEIGHT
    bottom_content_height = max(readout_content_height, chart_content_height)
    plot_h = rect.y + rect.height - CONTENT_MARGIN_Y - bottom_content_height - plot_y

    def to_y(v: float) -> float:
      return plot_y + plot_h - (v - TRANS_ROOM_TEMP_C) / (TRANS_OVER_TEMP_C - TRANS_ROOM_TEMP_C) * plot_h

    # Widths use fixed reference strings, not live text, so nothing shifts as digit counts change.
    value_width = _max_text_width(self._font_title, VALUE_WIDTH_REFERENCES, FONT_SIZES.current_speed)
    unit_width = _max_text_width(self._font_label, ("°C", "°F"), FONT_SIZES.current_speed // 2)
    readout_width = value_width + READOUT_UNIT_GAP + unit_width

    tick_label_width = _max_text_width(self._font_label, (f"{t:.0f}°" for t in GAUGE_TICK_VALUES), LABEL_FONT_SIZE)
    gauge_width = readout_width - GAUGE_COLUMN_GAP - tick_label_width

    # Chart is narrowed to reserve a column for the threshold labels, so they can't overlap the gridlines.
    region_label_width = _max_text_width(self._font_label, (tr(name) for name in THRESHOLD_LABELS), LABEL_FONT_SIZE)

    gauge_rect = rl.Rectangle(content_x, plot_y, gauge_width, plot_h)
    graph_x = gauge_rect.x + gauge_rect.width + GAUGE_COLUMN_GAP + tick_label_width + GAUGE_COLUMN_GAP
    graph_width = rect.x + rect.width - CONTENT_MARGIN_X - THRESHOLD_LABEL_GAP - region_label_width - graph_x
    graph_rect = rl.Rectangle(graph_x, plot_y, graph_width, plot_h)

    self._draw_gauge(gauge_rect, to_y, live_temp, tick_label_width)

    readout_rect = rl.Rectangle(content_x, gauge_rect.y + gauge_rect.height, readout_width, rect.y + rect.height - (gauge_rect.y + gauge_rect.height))
    self._draw_readout(readout_rect, live_temp, is_metric)

    if len(samples) < 2:
      self._draw_centered_text(graph_rect, tr("Gathering data..."))
      return

    def to_x(t: float) -> float:
      return graph_rect.x + (t - samples[0][0]) / max(samples[-1][0] - samples[0][0], 1.0) * graph_rect.width

    for temp, label in zip(THRESHOLDS, THRESHOLD_LABELS):
      self._draw_threshold_line(graph_rect, to_y, temp, tr(label))

    durations = dict.fromkeys(REGION_ORDER, 0.0)
    prev_t, prev_v = samples[0]
    for t, v in samples[1:]:
      for (ta, va), (tb, vb) in _split_at_thresholds(prev_t, prev_v, t, v):
        mid_v = (va + vb) / 2
        region = get_region_for_temp(mid_v)
        rl.draw_line_ex(rl.Vector2(to_x(ta), to_y(va)), rl.Vector2(to_x(tb), to_y(vb)), CHART_LINE_THICKNESS, get_color_for_temp(mid_v))
        durations[region] += tb - ta
      prev_t, prev_v = t, v

    self._draw_minmax_line(graph_rect, to_y, max(v for _, v in samples), "MAX", is_metric)

    self._draw_time_labels(graph_rect, to_x, samples[0][0], samples[-1][0])
    self._draw_region_tiles(rect, graph_rect, durations, _compute_rate(samples))

  def _draw_header(self, rect: rl.Rectangle, content_x: float) -> float:
    """Returns the y just below the title, so the plot can start a fixed gap below it regardless of font metrics."""
    title = tr("TRANS TEMP (PAN)")
    origin = rl.Vector2(content_x, rect.y + CONTENT_MARGIN_Y)
    size = measure_text_cached(self._font_title, title, FONT_SIZES.speed_unit)
    rl.draw_text_ex(self._font_title, title, origin, FONT_SIZES.speed_unit, 0, COLORS.WHITE)
    return origin.y + size.y

  def _draw_gauge(self, rect: rl.Rectangle, to_y, live_temp: float, tick_label_width: float) -> None:
    """`rect` shares plot_y/plot_h with the chart's graph_rect, so to_y(temp) lands on the same pixel row in both.

    The bar is drawn BORDER_THICKNESS narrower than `rect`: draw_rectangle_rounded_lines_ex's stroke bleeds
    outward past its own rect on straight edges, so shrinking the bar keeps that outward bleed - and thus the
    gauge's true visual edge - right at `rect`'s edge instead of past it.
    """
    bar_rect = rl.Rectangle(rect.x, rect.y, rect.width - BORDER_THICKNESS, rect.height)
    rl.draw_rectangle_rounded(bar_rect, ROUNDNESS, 10, rl.Color(255, 255, 255, 18))

    if not math.isnan(live_temp):
      fill_top = to_y(min(max(live_temp, TRANS_ROOM_TEMP_C), TRANS_OVER_TEMP_C))
      fill_height = bar_rect.y + bar_rect.height - fill_top
      rl.begin_scissor_mode(int(bar_rect.x), int(fill_top), int(bar_rect.width), int(fill_height) + 1)
      rl.draw_rectangle_rounded(bar_rect, ROUNDNESS, 10, get_color_for_temp(live_temp))
      rl.end_scissor_mode()

    rl.draw_rectangle_rounded_lines_ex(bar_rect, ROUNDNESS, 10, BORDER_THICKNESS, COLORS.WHITE_TRANSLUCENT)

    tick_label_right = rect.x + rect.width + GAUGE_COLUMN_GAP + tick_label_width
    for temp in GAUGE_TICK_VALUES:
      self._draw_label_at_y(f"{temp:.0f}°", tick_label_right, to_y(temp), COLORS.GREY, right_align=True)

  def _draw_readout(self, rect: rl.Rectangle, live_temp: float, is_metric: bool) -> None:
    """`rect` spans gauge-bottom to screen-bottom; the value is bottom-anchored CONTENT_MARGIN_Y above rect's bottom to match the region tiles' margin."""
    if math.isnan(live_temp):
      value_text, unit_text, color = "--", "", COLORS.GREY
    else:
      value, unit = _convert_temp(live_temp, is_metric)
      value_text, unit_text, color = f"{value:.0f}", f"°{unit}", get_color_for_temp(live_temp)

    value_size = measure_text_cached(self._font_title, value_text, FONT_SIZES.current_speed)
    origin_y = rect.y + rect.height - CONTENT_MARGIN_Y - value_size.y
    rl.draw_text_ex(self._font_title, value_text, rl.Vector2(rect.x, origin_y), FONT_SIZES.current_speed, 0, color)

    if unit_text:
      unit_font_size = FONT_SIZES.current_speed // 2
      value_ink_top = _ink_top_offset(self._font_title, value_text, FONT_SIZES.current_speed)
      unit_ink_top = _ink_top_offset(self._font_label, unit_text, unit_font_size)
      unit_origin = rl.Vector2(rect.x + value_size.x + READOUT_UNIT_GAP, origin_y + value_ink_top - unit_ink_top)
      rl.draw_text_ex(self._font_label, unit_text, unit_origin, unit_font_size, 0, color)

  def _draw_label_at_y(self, text: str, x: float, y: float, color: rl.Color, *, right_align: bool = False) -> None:
    """Draws `text` at LABEL_FONT_SIZE, vertically centered on y - shared by the gauge ticks and threshold lines."""
    size = measure_text_cached(self._font_label, text, LABEL_FONT_SIZE)
    origin_x = x - size.x if right_align else x
    rl.draw_text_ex(self._font_label, text, rl.Vector2(origin_x, y - size.y / 2), LABEL_FONT_SIZE, 0, color)

  def _draw_threshold_line(self, graph_rect: rl.Rectangle, to_y, temp: float, label: str) -> None:
    """The label sits in the fixed-width column reserved to the right of graph_rect (see _render)."""
    y = to_y(temp)
    rl.draw_line_ex(rl.Vector2(graph_rect.x, y), rl.Vector2(graph_rect.x + graph_rect.width, y), 2, GRID_COLOR)
    self._draw_label_at_y(label, graph_rect.x + graph_rect.width + THRESHOLD_LABEL_GAP, y, GRID_COLOR)

  def _draw_minmax_line(self, graph_rect: rl.Rectangle, to_y, value: float, tag: str, is_metric: bool) -> None:
    y = to_y(value)
    rl.draw_line_ex(rl.Vector2(graph_rect.x, y), rl.Vector2(graph_rect.x + graph_rect.width, y), 2, MINMAX_LINE_COLOR)

    display_value, unit = _convert_temp(value, is_metric)
    text = f"{tag} {display_value:.0f}°{unit}"
    text_size = measure_text_cached(self._font_label, text, LABEL_FONT_SIZE)
    label_y = y - text_size.y - 6
    if label_y < graph_rect.y:  # drop below the line instead of clipping above the graph
      label_y = y + 6
    rl.draw_text_ex(self._font_label, text, rl.Vector2(graph_rect.x, label_y), LABEL_FONT_SIZE, 0, MINMAX_LINE_COLOR)

  def _draw_time_labels(self, graph_rect: rl.Rectangle, to_x, t0: float, t1: float) -> None:
    tick_top = graph_rect.y + graph_rect.height
    label_y = tick_top + 16

    rl.draw_line_ex(rl.Vector2(graph_rect.x, tick_top), rl.Vector2(graph_rect.x + graph_rect.width, tick_top), 2, GRID_COLOR)

    span = max(t1 - t0, 1.0)
    interval = next((i for i in TIME_TICK_INTERVALS_S if span / i <= TIME_TICK_MAX_COUNT), TIME_TICK_INTERVALS_S[-1])
    num_ticks = int(span // interval)
    for i in range(num_ticks + 1):
      offset_s = i * interval
      x = to_x(t1 - offset_s)
      rl.draw_line_ex(rl.Vector2(x, tick_top), rl.Vector2(x, tick_top + 10), 2, GRID_COLOR)

      text = tr("now") if offset_s == 0 else _format_tick_offset(offset_s)
      text_width = measure_text_cached(self._font_label, text, LABEL_FONT_SIZE).x
      text_x = min(max(x - text_width / 2, graph_rect.x), graph_rect.x + graph_rect.width - text_width)
      rl.draw_text_ex(self._font_label, text, rl.Vector2(text_x, label_y), LABEL_FONT_SIZE, 0, COLORS.GREY)

  def _draw_region_tiles(self, rect: rl.Rectangle, graph_rect: rl.Rectangle, durations: dict[str, float], rate: float | None) -> None:
    """Bottom-anchored CONTENT_MARGIN_Y above rect's bottom edge to match the readout's margin."""
    tile_y = rect.y + rect.height - CONTENT_MARGIN_Y - REGION_TILE_HEIGHT
    tile_count = len(REGION_ORDER) + 1  # +1 for the rate-of-change slot, leftmost in the row
    tile_width = (graph_rect.width - REGION_TILE_GAP * (tile_count - 1)) / tile_count

    def tile_rect_at(i: int) -> rl.Rectangle:
      return rl.Rectangle(graph_rect.x + i * (tile_width + REGION_TILE_GAP), tile_y, tile_width, REGION_TILE_HEIGHT)

    self._draw_rate_stat(tile_rect_at(0), rate)

    for i, region in enumerate(REGION_ORDER):
      tile_rect = tile_rect_at(i + 1)
      has_time = durations[region] > 0
      color = REGION_COLORS[region] if has_time else COLORS.GREY
      value_text = _format_duration(durations[region]) if has_time else "-"
      self._draw_stat_tile(tile_rect, tr(region), value_text, color)

  def _draw_rate_stat(self, tile_rect: rl.Rectangle, rate: float | None) -> None:
    """Plain text, no tile background/label like its neighbors - a live instantaneous stat, not a session duration."""
    if rate is None:
      color, text = COLORS.GREY, "-"
    else:
      if rate > RATE_STEADY_THRESHOLD_C_S:
        color = REGION_COLORS["HOT"]
      elif rate < -RATE_STEADY_THRESHOLD_C_S:
        color = REGION_COLORS["COLD"]
      else:
        color = COLORS.WHITE_TRANSLUCENT
      text = f"{rate:+.1f}°/s"

    padding = 8  # small breathing room so the text doesn't touch the neighboring tile or the row's edges
    font_size = _max_font_size_to_fit(self._font_title, text, tile_rect.width - padding * 2, tile_rect.height - padding * 2)
    text_size = measure_text_cached(self._font_title, text, font_size)
    origin = rl.Vector2(tile_rect.x + tile_rect.width / 2 - text_size.x / 2, tile_rect.y + tile_rect.height / 2 - text_size.y / 2)
    rl.draw_text_ex(self._font_title, text, origin, font_size, 0, color)

  def _draw_stat_tile(self, tile_rect: rl.Rectangle, label: str, value_text: str, color: rl.Color) -> None:
    _draw_rounded_tile(tile_rect, rl.Color(255, 255, 255, 18), rl.Color(color.r, color.g, color.b, 130), border_thickness=2)

    items = [
      _text_item(self._font_label, label, REGION_TILE_LABEL_FONT_SIZE, COLORS.GREY),
      _text_item(self._font_title, value_text, REGION_TILE_VALUE_FONT_SIZE, color),
    ]
    block_height = sum(item.size.y for item in items) + 8
    block_y = tile_rect.y + tile_rect.height / 2 - block_height / 2

    _draw_centered_stack(items, tile_rect.x + tile_rect.width / 2, block_y, gap=8)

  def _draw_centered_text(self, rect: rl.Rectangle, text: str) -> None:
    size = measure_text_cached(self._font_label, text, LABEL_FONT_SIZE)
    origin = rl.Vector2(rect.x + rect.width / 2 - size.x / 2, rect.y + rect.height / 2 - size.y / 2)
    rl.draw_text_ex(self._font_label, text, origin, LABEL_FONT_SIZE, 0, COLORS.GREY)
