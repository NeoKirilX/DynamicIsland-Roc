
from __future__ import annotations

import cairo

try:
    from settings import Settings
except ImportError:
    from .settings import Settings

class _Cell:

    def __init__(self, char: str) -> None:
        self.char: str = char
        self.old_char: str | None = None
        self.leave_elapsed: float = 0.0
        self.enter_elapsed: float = 0.0
        self.is_animating: bool = False
        self.down: bool = True

class Digits:

    LEAVE_DURATION: float = 0.26
    LEAVE_FADE_DURATION: float = 0.20
    ENTER_DURATION: float = 0.38
    ENTER_FADE_DURATION: float = 0.26

    def __init__(
        self,
        text: str = "",
        down: bool = True,
        font_family: str | None = "sans-serif",
    ) -> None:
        self.down: bool = bool(down)
        self.font_family: str | None = font_family

        self._text: str = ""
        self._cells: list[_Cell] = []
        self._initialized: bool = False

        if text:
            self.set_text(text)

    @property
    def text(self) -> str:
        return self._text

    @property
    def is_animating(self) -> bool:
        return any(c.is_animating for c in self._cells)

    def set_text(self, text: str) -> None:
        text = str(text) if text is not None else ""
        if text == self._text:
            return

        self._text = text

        if not self._initialized:
            self._cells = [_Cell(ch) for ch in text]
            self._initialized = True
            return

        while len(self._cells) > len(text):
            self._cells.pop(0)
        while len(self._cells) < len(text):
            self._cells.insert(0, _Cell(""))

        for i, new_ch in enumerate(text):
            cell = self._cells[i]
            if cell.char == new_ch and not cell.is_animating:
                continue

            old_ch = cell.char if cell.char else None
            cell.old_char = old_ch
            cell.char = new_ch
            cell.leave_elapsed = 0.0
            cell.enter_elapsed = 0.0
            cell.is_animating = True
            cell.down = self.down

    def tick(self, dt: float) -> bool:
        dt = max(0.0, float(dt))
        any_moving = False

        for cell in self._cells:
            if not cell.is_animating:
                continue

            cell.leave_elapsed += dt
            cell.enter_elapsed += dt

            if cell.leave_elapsed >= self.LEAVE_DURATION:
                cell.old_char = None

            if (
                cell.enter_elapsed >= self.ENTER_DURATION
                and cell.old_char is None
            ):
                cell.is_animating = False
            else:
                any_moving = True

        return any_moving

    def render(
        self,
        cr: cairo.Context,
        x: float,
        y: float,
        font_size: float,
        color: tuple[float, float, float]
        | tuple[float, float, float, float] = (1.0, 1.0, 1.0),
        align: str = "right",
        valign: str = "top",
    ) -> None:
        font_size = font_size * Settings.text_factor()
        if not self._cells or font_size <= 0.0:
            return

        r = color[0]
        g = color[1]
        b = color[2]
        base_alpha = color[3] if len(color) > 3 else 1.0

        cr.save()
        if self.font_family is not None:
            cr.select_font_face(
                self.font_family,
                cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_NORMAL,
            )
        cr.set_font_size(font_size)

        fe_ascent, fe_descent, fe_height, _, _ = cr.font_extents()
        if valign == "baseline":
            baseline = y
        elif valign == "center":
            baseline = y + fe_ascent - (fe_ascent + fe_descent) / 2.0
        else:
            baseline = y + fe_ascent

        travel = max(1.0, round(font_size * 0.5))

        digit_advance = max(
            cr.text_extents(str(d)).x_advance for d in range(10)
        )

        cell_widths: list[float] = []
        for cell in self._cells:
            c = cell.char or (cell.old_char or " ")
            if "0" <= c <= "9":
                cw = digit_advance
            else:
                cw = cr.text_extents(c).x_advance
            cell_widths.append(cw)

        total_width = sum(cell_widths)
        align_lower = align.lower()
        if align_lower == "right":
            cur_x = x - total_width
        elif align_lower == "center":
            cur_x = x - total_width / 2.0
        else:
            cur_x = x

        for cell, cw in zip(self._cells, cell_widths):
            if cell.old_char is not None and cell.is_animating:
                t_leave = min(1.0, cell.leave_elapsed / self.LEAVE_DURATION)
                ease_leave = t_leave**3
                dy_leave = (travel if cell.down else -travel) * ease_leave

                t_fade = min(1.0, cell.leave_elapsed / self.LEAVE_FADE_DURATION)
                alpha_leave = max(0.0, 1.0 - t_fade) * base_alpha

                if alpha_leave > 0.001:
                    te_old = cr.text_extents(cell.old_char)
                    glyph_x = cur_x + (cw - te_old.x_advance) / 2.0
                    cr.move_to(glyph_x, baseline + dy_leave)
                    cr.set_source_rgba(r, g, b, alpha_leave)
                    cr.show_text(cell.old_char)

            if cell.char:
                if cell.is_animating:
                    t_enter = min(1.0, cell.enter_elapsed / self.ENTER_DURATION)
                    ease_enter = 1.0 - (1.0 - t_enter) ** 3
                    dy_enter = (
                        -travel if cell.down else travel
                    ) * (1.0 - ease_enter)

                    t_fade = min(
                        1.0, cell.enter_elapsed / self.ENTER_FADE_DURATION
                    )
                    alpha_enter = min(1.0, t_fade) * base_alpha
                else:
                    dy_enter = 0.0
                    alpha_enter = base_alpha

                if alpha_enter > 0.001:
                    te_curr = cr.text_extents(cell.char)
                    glyph_x = cur_x + (cw - te_curr.x_advance) / 2.0
                    cr.move_to(glyph_x, baseline + dy_enter)
                    cr.set_source_rgba(r, g, b, alpha_enter)
                    cr.show_text(cell.char)

            cur_x += cw

        cr.restore()

if __name__ == "__main__":
    print("Testing Digits component...")

    digits = Digits("25:00", down=True)
    assert digits.text == "25:00", f"Expected '25:00', got {digits.text}"
    assert not digits.is_animating, "Initial text should not be animating"

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 50)
    cr = cairo.Context(surface)
    digits.render(cr, x=180, y=10, font_size=24.0, color=(1.0, 1.0, 1.0), align="right")
    print("Rendered initial static digits successfully.")

    digits.set_text("24:59")
    assert digits.is_animating, "Digits should be animating after change"

    assert not digits._cells[0].is_animating, "'2' should not move"
    assert digits._cells[1].is_animating, "'5'->'4' should move"
    assert not digits._cells[2].is_animating, "':' should not move"
    assert digits._cells[3].is_animating, "'0'->'5' should move"
    assert digits._cells[4].is_animating, "'0'->'9' should move"
    print("Selective digit animation verified: unchanged characters stay static.")

    moved = digits.tick(0.15)
    assert moved, "tick should return True while moving"
    digits.render(cr, x=180, y=10, font_size=24.0, color=(1.0, 1.0, 1.0), align="right")

    for _ in range(10):
        digits.tick(0.05)
    assert not digits.is_animating, "Animation should be complete"
    print("Countdown transition animation completed.")

    digits.set_text("9")
    assert len(digits._cells) == 1
    assert digits.text == "9"
    digits.tick(0.50)
    assert not digits.is_animating

    digits.set_text("100")
    assert len(digits._cells) == 3
    digits.tick(0.50)
    assert not digits.is_animating

    countup_digits = Digits("10", down=False)
    countup_digits.set_text("11")
    assert countup_digits.is_animating
    assert not countup_digits._cells[0].is_animating
    assert countup_digits._cells[1].is_animating
    assert countup_digits._cells[1].down is False

    countup_digits.render(cr, x=50, y=10, font_size=20.0, color=(0.2, 0.8, 0.4), align="left")
    countup_digits.tick(0.50)
    assert not countup_digits.is_animating

    print("All Digits component tests passed successfully!")
