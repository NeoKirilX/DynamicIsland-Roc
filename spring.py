
from __future__ import annotations

class Spring:

    STEP: float = 1.0 / 240.0

    def __init__(
        self,
        value: float,
        stiffness: float = 300.0,
        damping: float = 24.0,
    ) -> None:
        self.value: float = float(value)
        self.target: float = float(value)
        self.velocity: float = 0.0
        self.stiffness: float = float(stiffness)
        self.damping: float = float(damping)

    def tune(self, stiffness: float, damping: float) -> None:
        self.stiffness = float(stiffness)
        self.damping = float(damping)

    def advance(self, dt: float) -> bool:
        if self.value == self.target and self.velocity == 0.0:
            return False

        while dt > 0.0:
            h = min(self.STEP, dt)
            accel = (
                -self.stiffness * (self.value - self.target)
                - self.damping * self.velocity
            )
            self.velocity += accel * h
            self.value += self.velocity * h
            dt -= h

        if abs(self.value - self.target) < 0.005 and abs(self.velocity) < 0.05:
            self.value = self.target
            self.velocity = 0.0
            return False
        return True

if __name__ == "__main__":
    s = Spring(0.0)
    s.target = 100.0
    dt = 1.0 / 60.0
    steps = 0

    while s.advance(dt) and steps < 600:
        steps += 1

    print(
        f"Spring test: converged to {s.value:.4f} in {steps} steps "
        f"(target={s.target})"
    )
    assert abs(s.value - 100.0) < 1e-6, "Spring did not converge to target"
    assert s.velocity == 0.0, "Spring velocity at rest is not 0"
    print("All Spring unit tests passed successfully!")
