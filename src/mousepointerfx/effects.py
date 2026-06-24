"""클릭 리플 / 레이저 트레일의 수명·기하 계산.

순수 로직(시간은 인자로 주입) → GUI 없이 단위 테스트 가능.
색은 hex 문자열로 보관하고, 실제 픽셀 그리기는 overlay/renderer가 담당한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass
class Ripple:
    """클릭 시 퍼지는 효과 한 개.

    x, y      : 중심(px)
    color     : hex 문자열
    max_radius: 최대 반지름(px)
    duration  : 지속 시간(초)
    thickness : 선 두께(px)
    style     : ripple | rings | burst | highlight
    start     : 생성 시각(초, monotonic)
    """

    x: float
    y: float
    color: str
    max_radius: float
    duration: float
    thickness: float
    start: float
    style: str = "ripple"

    def progress(self, now: float) -> float:
        if self.duration <= 0:
            return 1.0
        return _clamp((now - self.start) / self.duration)

    def is_expired(self, now: float) -> bool:
        return self.progress(now) >= 1.0

    def radius(self, now: float) -> float:
        """ease-out 으로 빠르게 커졌다 느려짐."""
        p = self.progress(now)
        eased = 1.0 - (1.0 - p) * (1.0 - p)
        return self.max_radius * eased

    def alpha(self, now: float) -> float:
        """0..1, 시간이 지날수록 옅어짐."""
        return 1.0 - self.progress(now)


class ClickEffects:
    """활성 리플들의 컬렉션."""

    def __init__(self) -> None:
        self._ripples: list[Ripple] = []

    def add(self, ripple: Ripple) -> None:
        self._ripples.append(ripple)

    def update(self, now: float) -> None:
        """만료된 리플 제거."""
        self._ripples = [r for r in self._ripples if not r.is_expired(now)]

    def items(self) -> list[Ripple]:
        return list(self._ripples)

    def __len__(self) -> int:
        return len(self._ripples)

    def active(self, now: float) -> bool:
        return any(not r.is_expired(now) for r in self._ripples)


@dataclass
class TrailPoint:
    x: float
    y: float
    birth: float


@dataclass
class LaserTrail:
    """레이저 점 뒤로 따라오는 페이드 잔상.

    lifetime: 한 점이 사라지기까지 시간(초)
    max_points: 보관 최대 개수(과도한 누적 방지)
    """

    lifetime: float
    max_points: int = 240
    _points: list[TrailPoint] = field(default_factory=list)

    def add(self, x: float, y: float, now: float) -> None:
        pts = self._points
        # 같은 위치 연속 추가 방지(미세 이동만 기록)
        if pts:
            last = pts[-1]
            if abs(last.x - x) < 0.5 and abs(last.y - y) < 0.5:
                last.birth = now  # 위치 같으면 수명만 갱신
                return
        pts.append(TrailPoint(x, y, now))
        if len(pts) > self.max_points:
            del pts[: len(pts) - self.max_points]

    def prune(self, now: float) -> None:
        cutoff = now - self.lifetime
        self._points = [p for p in self._points if p.birth >= cutoff]

    def points_with_alpha(self, now: float) -> list[tuple[float, float, float]]:
        """각 점의 (x, y, alpha[0..1])를 오래된→최신 순으로 반환."""
        if self.lifetime <= 0:
            return [(p.x, p.y, 1.0) for p in self._points]
        out: list[tuple[float, float, float]] = []
        for p in self._points:
            age = now - p.birth
            a = _clamp(1.0 - age / self.lifetime)
            if a > 0.0:
                out.append((p.x, p.y, a))
        return out

    def clear(self) -> None:
        self._points.clear()

    def __len__(self) -> int:
        return len(self._points)
