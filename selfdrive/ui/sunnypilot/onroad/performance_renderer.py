"""
Copyright (c) 2026 Kevin Yeh

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import math
from collections import deque
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
  GRAPH_MARGIN_BOTTOM,
  GRAPH_MARGIN_TOP,
  GRAPH_MARGIN_X,
  GRID_COLOR,
  HISTORY_MAXLEN,
  HISTORY_SAMPLE_INTERVAL_S,
  LABEL_FONT_SIZE,
  LEFT_MARGIN,
  LINE_THICKNESS,
  MINMAX_LINE_COLOR,
  REGION_TILE_GAP,
  REGION_TILE_HEIGHT,
  REGION_TILE_LABEL_FONT_SIZE,
  REGION_TILE_VALUE_FONT_SIZE,
  THRESHOLDS,
  TILE_PADDING,
  TILE_ROUNDNESS,
  TIME_TICK_INTERVALS_S,
  TIME_TICK_MAX_COUNT,
  TRANS_COLD_TEMP_C,
  TRANS_CRIT_TEMP_C,
  TRANS_ROOM_TEMP_C,
  TRANS_WARN_TEMP_C,
  VALUE_WIDTH_REFERENCES,
)
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget


def read_trans_oil_temp() -> float:
  sm = ui_state.sm
  if sm.recv_frame["carStateSP"] < ui_state.started_frame:
    return float('nan')
  return sm["carStateSP"].transOilTemp


def sample_if_due(history: deque[tuple[float, float]], trans_oil_temp: float) -> None:
  """Append a (time, value) sample at most once per HISTORY_SAMPLE_INTERVAL_S.

  Must be called from whichever of PerformanceRenderer/PerformanceGraph is actually being
  rendered this frame: only the top-of-nav-stack widget renders, so when the graph overlay is
  open, PerformanceRenderer stops rendering (and thus stops updating) entirely - sampling can't
  live in just one of them or history freezes whenever the other one is on screen.
  """
  if math.isnan(trans_oil_temp):
    return
  now = rl.get_time()
  if history and now - history[-1][0] < HISTORY_SAMPLE_INTERVAL_S:
    return
  history.append((now, trans_oil_temp))


def _split_at_thresholds(t0: float, v0: float, t1: float, v1: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
  """Split a (t0,v0)->(t1,v1) segment at every threshold it crosses, so callers can attribute an
  exact sub-range of time/pixels to the region on each side, instead of the whole segment."""
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


def _format_tick_offset(offset_s: int) -> str:
  """Format a "-<offset>" time-axis tick label. Unlike _format_duration, this must not floor a
  non-round-minute offset (e.g. 75s) down to "-1m" - TIME_TICK_INTERVALS_S entries like 15/30
  don't always divide evenly into minutes, so distinct ticks would otherwise collide on one label."""
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


def _text_item(font: rl.Font, text: str, font_size: int, color: rl.Color) -> _TextItem:
  return _TextItem(font, text, measure_text_cached(font, text, font_size), font_size, color)


def _draw_centered_stack(items: list[_TextItem], center_x: float, top_y: float, gap: float = 0) -> None:
  """Draw texts stacked vertically, each horizontally centered on center_x."""
  y = top_y
  for item in items:
    rl.draw_text_ex(item.font, item.text, rl.Vector2(center_x - item.size.x / 2, y), item.font_size, 0, item.color)
    y += item.size.y + gap


def _draw_rounded_tile(rect: rl.Rectangle, bg_color: rl.Color, border_color: rl.Color, border_thickness: float = 10) -> None:
  rl.draw_rectangle_rounded(rect, TILE_ROUNDNESS, 10, bg_color)
  rl.draw_rectangle_rounded_lines_ex(rect, TILE_ROUNDNESS, 10, border_thickness, border_color)


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
    # Restrict taps to the visible tile, not the full HUD rect this widget is rendered into.
    return self._tile_rect

  def update(self):
    self.trans_oil_temp = read_trans_oil_temp()
    sample_if_due(self.history, self.trans_oil_temp)

  def _render(self, rect: rl.Rectangle) -> None:
    if math.isnan(self.trans_oil_temp):
      self._tile_rect = rl.Rectangle(0, 0, 0, 0)
      return

    is_metric = True  # TODO: temporarily hardcoded to Celsius for testing
    # is_metric = ui_state.is_metric
    value, unit = _convert_temp(self.trans_oil_temp, is_metric)
    color = get_color_for_temp(self.trans_oil_temp)

    items = [
      _text_item(self.font_label, tr("TRANS"), FONT_SIZES.speed_unit, COLORS.GREY),
      _text_item(self.font, f"{value:.0f}", FONT_SIZES.current_speed, color),
      _text_item(self.font_label, f"°{unit}", FONT_SIZES.speed_unit, COLORS.GREY),
    ]
    value_width = max(measure_text_cached(self.font, ref, FONT_SIZES.current_speed).x for ref in VALUE_WIDTH_REFERENCES)

    block_width = max(value_width, *(item.size.x for item in items))
    block_height = sum(item.size.y for item in items)
    block_y = rect.y + rect.height / 2 - block_height / 2

    tile_rect = rl.Rectangle(
      rect.x + LEFT_MARGIN - TILE_PADDING,
      block_y - TILE_PADDING,
      block_width + TILE_PADDING * 2,
      block_height + TILE_PADDING * 2,
    )
    _draw_rounded_tile(tile_rect, TILE_BG_COLOR, color)
    self._tile_rect = tile_rect

    _draw_centered_stack(items, rect.x + LEFT_MARGIN + block_width / 2, block_y)


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

    is_metric = True  # TODO: temporarily hardcoded to Celsius for testing
    # is_metric = ui_state.is_metric

    # Keep sampling while this overlay is the one actually rendering - PerformanceRenderer stops
    # rendering (and thus stops sampling) whenever this graph is on top of the nav stack.
    live_temp = read_trans_oil_temp()
    sample_if_due(self._history, live_temp)

    samples = list(self._history)
    self._draw_header(rect, None if math.isnan(live_temp) else live_temp, is_metric)

    graph_rect = rl.Rectangle(
      rect.x + GRAPH_MARGIN_X,
      rect.y + GRAPH_MARGIN_TOP,
      rect.width - GRAPH_MARGIN_X * 2,
      rect.height - GRAPH_MARGIN_TOP - GRAPH_MARGIN_BOTTOM,
    )

    if len(samples) < 2:
      self._draw_centered_text(graph_rect, tr("Gathering data..."))
      return

    values = [v for _, v in samples]
    min_val = min(*values, TRANS_ROOM_TEMP_C)
    max_val = max(*values, TRANS_WARN_TEMP_C)

    def to_x(t: float) -> float:
      return graph_rect.x + (t - samples[0][0]) / max(samples[-1][0] - samples[0][0], 1.0) * graph_rect.width

    def to_y(v: float) -> float:
      return graph_rect.y + graph_rect.height - (v - min_val) / (max_val - min_val) * graph_rect.height

    # "CRITICAL" doesn't fit the margin here without overlapping the gridline, unlike the tile below.
    for temp, label in zip(THRESHOLDS, ("COLD", "WARN", "CRIT")):
      if min_val <= temp <= max_val:
        self._draw_threshold_line(rect, graph_rect, to_y, temp, tr(label), is_metric)

    durations = dict.fromkeys(REGION_ORDER, 0.0)
    prev_t, prev_v = samples[0]
    for t, v in samples[1:]:
      for (ta, va), (tb, vb) in _split_at_thresholds(prev_t, prev_v, t, v):
        mid_v = (va + vb) / 2
        region = get_region_for_temp(mid_v)
        rl.draw_line_ex(rl.Vector2(to_x(ta), to_y(va)), rl.Vector2(to_x(tb), to_y(vb)), LINE_THICKNESS, get_color_for_temp(mid_v))
        durations[region] += tb - ta
      prev_t, prev_v = t, v

    self._draw_axis_floor_label(graph_rect, min_val, is_metric)
    self._draw_minmax_line(graph_rect, to_y, max(values), "MAX", is_metric)

    self._draw_time_labels(graph_rect, to_x, samples[0][0], samples[-1][0])
    self._draw_region_tiles(graph_rect, durations)

  def _draw_header(self, rect: rl.Rectangle, current_temp: float | None, is_metric: bool) -> None:
    # Both pinned to the left, closest to the driver's eyeline, with the title and value close
    # together as one unit rather than split to opposite corners.
    title = tr("TRANS TEMP")
    title_size = measure_text_cached(self._font_title, title, FONT_SIZES.speed_unit)
    title_origin = rl.Vector2(rect.x + GRAPH_MARGIN_X, rect.y + 60)
    rl.draw_text_ex(self._font_title, title, title_origin, FONT_SIZES.speed_unit, 0, COLORS.WHITE)

    if current_temp is None:
      return
    value, unit = _convert_temp(current_temp, is_metric)
    value_text = f"{value:.0f}{unit}"
    value_origin = rl.Vector2(title_origin.x + title_size.x + 30, rect.y + 60)
    rl.draw_text_ex(self._font_title, value_text, value_origin, FONT_SIZES.speed_unit, 0, get_color_for_temp(current_temp))

  def _draw_threshold_line(self, rect: rl.Rectangle, graph_rect: rl.Rectangle, to_y, temp: float, label: str, is_metric: bool) -> None:
    y = to_y(temp)
    rl.draw_line_ex(rl.Vector2(graph_rect.x, y), rl.Vector2(graph_rect.x + graph_rect.width, y), 2, GRID_COLOR)

    value, unit = _convert_temp(temp, is_metric)
    value_text = f"{value:.0f}{unit}"
    value_width = measure_text_cached(self._font_label, value_text, LABEL_FONT_SIZE).x
    value_origin = rl.Vector2(graph_rect.x - value_width - 20, y - LABEL_FONT_SIZE / 2)
    rl.draw_text_ex(self._font_label, value_text, value_origin, LABEL_FONT_SIZE, 0, COLORS.GREY)

    label_width = measure_text_cached(self._font_label, label, LABEL_FONT_SIZE).x
    label_x = min(graph_rect.x + graph_rect.width + 10, rect.x + rect.width - label_width - 10)
    rl.draw_text_ex(self._font_label, label, rl.Vector2(label_x, y - LABEL_FONT_SIZE / 2), LABEL_FONT_SIZE, 0, GRID_COLOR)

  def _draw_axis_floor_label(self, graph_rect: rl.Rectangle, min_val: float, is_metric: bool) -> None:
    """Labels the y-axis floor at the x-axis baseline, in the same left column as the threshold
    value labels - unlike those, there's no line to draw since the floor already is the bottom
    edge of graph_rect."""
    value, unit = _convert_temp(min_val, is_metric)
    text = f"{value:.0f}{unit}"
    text_width = measure_text_cached(self._font_label, text, LABEL_FONT_SIZE).x
    y = graph_rect.y + graph_rect.height
    origin = rl.Vector2(graph_rect.x - text_width - 20, y - LABEL_FONT_SIZE / 2)
    rl.draw_text_ex(self._font_label, text, origin, LABEL_FONT_SIZE, 0, COLORS.GREY)

  def _draw_minmax_line(self, graph_rect: rl.Rectangle, to_y, value: float, tag: str, is_metric: bool) -> None:
    y = to_y(value)
    rl.draw_line_ex(rl.Vector2(graph_rect.x, y), rl.Vector2(graph_rect.x + graph_rect.width, y), 2, MINMAX_LINE_COLOR)

    display_value, unit = _convert_temp(value, is_metric)
    text = f"{tag} {display_value:.0f}°{unit}"
    text_size = measure_text_cached(self._font_label, text, LABEL_FONT_SIZE)
    # Label sits just above the line, at the plot's left edge (a different column than the
    # threshold labels, which sit outside the axis) - unless that would clip above the graph, in
    # which case it drops below the line instead (e.g. MAX sitting near the very top).
    label_y = y - text_size.y - 6
    if label_y < graph_rect.y:
      label_y = y + 6
    rl.draw_text_ex(self._font_label, text, rl.Vector2(graph_rect.x, label_y), LABEL_FONT_SIZE, 0, MINMAX_LINE_COLOR)

  def _draw_time_labels(self, graph_rect: rl.Rectangle, to_x, t0: float, t1: float) -> None:
    tick_top = graph_rect.y + graph_rect.height
    label_y = tick_top + 16

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

  def _draw_region_tiles(self, graph_rect: rl.Rectangle, durations: dict[str, float]) -> None:
    tile_y = graph_rect.y + graph_rect.height + 80
    tile_width = (graph_rect.width - REGION_TILE_GAP * (len(REGION_ORDER) - 1)) / len(REGION_ORDER)

    for i, region in enumerate(REGION_ORDER):
      tile_rect = rl.Rectangle(graph_rect.x + i * (tile_width + REGION_TILE_GAP), tile_y, tile_width, REGION_TILE_HEIGHT)
      has_time = durations[region] > 0
      color = REGION_COLORS[region] if has_time else COLORS.GREY
      value_text = _format_duration(durations[region]) if has_time else "-"

      _draw_rounded_tile(tile_rect, rl.Color(255, 255, 255, 18), rl.Color(color.r, color.g, color.b, 130), border_thickness=2)

      # Region keys are already their own display text ("COLD", "NORMAL", "WARN", "CRITICAL").
      items = [
        _text_item(self._font_label, tr(region), REGION_TILE_LABEL_FONT_SIZE, COLORS.GREY),
        _text_item(self._font_title, value_text, REGION_TILE_VALUE_FONT_SIZE, color),
      ]
      block_height = sum(item.size.y for item in items) + 8
      block_y = tile_rect.y + tile_rect.height / 2 - block_height / 2

      _draw_centered_stack(items, tile_rect.x + tile_rect.width / 2, block_y, gap=8)

  def _draw_centered_text(self, rect: rl.Rectangle, text: str) -> None:
    size = measure_text_cached(self._font_label, text, LABEL_FONT_SIZE)
    origin = rl.Vector2(rect.x + rect.width / 2 - size.x / 2, rect.y + rect.height / 2 - size.y / 2)
    rl.draw_text_ex(self._font_label, text, origin, LABEL_FONT_SIZE, 0, COLORS.GREY)
