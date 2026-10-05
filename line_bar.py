#!/usr/bin/env python3

from __future__ import annotations
import math
from typing import Sequence
import cairo

MARK_GAP: float = 2.0
MIN_SEGMENT_WIDTH: float = 6.0
SNAP_REACH: float = 5.0
PASSED_OPACITY: float = 0.85
AHEAD_OPACITY: float = 0.30
UNPLAYED_COLOR: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.20)

class LineBar:
    def __init__(self) -> None:
        self.starts: list[float] = []

    def set_starts(self, fractions: Sequence[float]) -> None:
        self.starts = [float(f) for f in fractions if 0.0 <= f <= 1.0]

    def compute_edges(self, width: float) -> list[float]:
        if width <= 0:
            return [0.0, 0.0]
        edges: list[float] = [0.0]
        for s in self.starts:
            x = s * width
            if (x - edges[-1] >= MIN_SEGMENT_WIDTH) and (width - x >= MIN_SEGMENT_WIDTH):
                edges.append(x)
        edges.append(width)
        return edges

    def snap(self, x: float, width: float) -> float:
        edges = self.compute_edges(width)
        nearest = x
        for i in range(1, len(edges) - 1):
            edge = edges[i]
            if abs(edge - x) <= SNAP_REACH and abs(edge - x) < abs(nearest - x):
                nearest = edge
        return nearest

    def render(
        self,
        cr: cairo.Context,
        x: float,
        y: float,
        width: float,
        height: float,
        progress: float,
        accent_color: tuple[float, float, float],
        alpha: float = 1.0,
    ) -> None:
        if width <= 0 or height <= 0:
            return

        edges = self.compute_edges(width)
        last = len(edges) - 2
        fill = max(0.0, min(width, progress * width))

        current = 0
        while current < last and edges[current + 1] <= fill:
            current += 1

        for i in range(last + 1):
            left = edges[i] + (MARK_GAP / 2.0 if i > 0 else 0.0)
            right = edges[i + 1] - (MARK_GAP / 2.0 if i < last else 0.0)
            seg_w = right - left
            if seg_w <= 0:
                continue

            radius = min(height, seg_w) / 2.0
            seg_x = x + left
            seg_y = y

            if i != current:
                if i < current:
                    cr.set_source_rgba(1.0, 1.0, 1.0, PASSED_OPACITY * alpha)
                else:
                    cr.set_source_rgba(
                        UNPLAYED_COLOR[0], UNPLAYED_COLOR[1], UNPLAYED_COLOR[2], UNPLAYED_COLOR[3] * alpha
                    )
                _draw_round_rect(cr, seg_x, seg_y, seg_w, height, radius)
                cr.fill()
                continue

            cr.set_source_rgba(
                accent_color[0], accent_color[1], accent_color[2], AHEAD_OPACITY * alpha
            )
            _draw_round_rect(cr, seg_x, seg_y, seg_w, height, radius)
            cr.fill()

            if fill > left:
                cr.save()
                clip_w = min(seg_w, fill - left)
                cr.rectangle(seg_x, seg_y, clip_w, height)
                cr.clip()
                cr.set_source_rgba(
                    accent_color[0], accent_color[1], accent_color[2], 1.0 * alpha
                )
                _draw_round_rect(cr, seg_x, seg_y, seg_w, height, radius)
                cr.fill()
                cr.restore()

def _draw_round_rect(cr: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()
