
from __future__ import annotations

import math

import cairo

class Ring:

    DEFAULT_THICKNESS: float = 2.5

    def __init__(
        self,
        thickness: float = DEFAULT_THICKNESS,
        progress: float = 1.0,
        color: tuple[float, float, float]
        | tuple[float, float, float, float] = (1.0, 1.0, 1.0),
    ) -> None:
        self.thickness: float = float(thickness)
        self.progress: float = float(progress)
        self.color: tuple[float, float, float] | tuple[
            float, float, float, float
        ] = color

    @staticmethod
    def render(
        cr: cairo.Context,
        cx: float,
        cy: float,
        radius: float,
        progress: float,
        color: tuple[float, float, float]
        | tuple[float, float, float, float] = (1.0, 1.0, 1.0),
        thickness: float = DEFAULT_THICKNESS,
    ) -> None:
        r = radius - thickness / 2.0
        if r <= 0.0 or thickness <= 0.0:
            return

        red = color[0]
        green = color[1]
        blue = color[2]
        base_alpha = color[3] if len(color) > 3 else 1.0

        cr.save()
        cr.set_line_width(thickness)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        cr.new_sub_path()
        cr.arc(cx, cy, r, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(red, green, blue, 0.3 * base_alpha)
        cr.stroke()

        share = max(0.0, min(1.0, float(progress)))
        if share > 0.001:
            cr.set_source_rgba(red, green, blue, base_alpha)
            if share >= 0.999:
                cr.new_sub_path()
                cr.arc(cx, cy, r, 0.0, 2.0 * math.pi)
                cr.stroke()
            else:
                start_angle = -math.pi / 2.0 + 2.0 * math.pi * (1.0 - share)
                end_angle = 3.0 * math.pi / 2.0
                cr.new_sub_path()
                cr.arc(cx, cy, r, start_angle, end_angle)
                cr.stroke()

        cr.restore()

    def draw(self, cr: cairo.Context, cx: float, cy: float, radius: float) -> None:
        self.render(
            cr,
            cx=cx,
            cy=cy,
            radius=radius,
            progress=self.progress,
            color=self.color,
            thickness=self.thickness,
        )

if __name__ == "__main__":
    print("Testing Ring component...")

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
    cr = cairo.Context(surf)

    Ring.render(
        cr,
        cx=50,
        cy=50,
        radius=40,
        progress=1.0,
        color=(1.0, 0.5, 0.0),
        thickness=2.5,
    )
    print("Full ring rendered successfully.")

    Ring.render(
        cr,
        cx=50,
        cy=50,
        radius=40,
        progress=0.6,
        color=(1.0, 1.0, 1.0),
        thickness=3.0,
    )
    print("Partial ring (60%) rendered successfully.")

    Ring.render(
        cr,
        cx=50,
        cy=50,
        radius=40,
        progress=0.0,
        color=(1.0, 1.0, 1.0),
        thickness=2.5,
    )
    print("Empty ring rendered successfully.")

    ring_obj = Ring(thickness=3.5, progress=0.25, color=(0.2, 0.8, 0.4))
    ring_obj.draw(cr, cx=50, cy=50, radius=40)
    print("Instance draw method tested successfully.")

    data = surf.get_data()
    assert any(b != 0 for b in data), "Expected non-zero pixels on surface"

    print("All Ring component tests passed successfully!")
