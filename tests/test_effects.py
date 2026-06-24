"""effects 모듈 단위 테스트(시간 주입으로 결정적 검증)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mousepointerfx.effects import ClickEffects, LaserTrail, Ripple  # noqa: E402


def make_ripple(start=0.0, duration=1.0, max_radius=100.0):
    return Ripple(x=10, y=20, color="#FF0000", max_radius=max_radius,
                  duration=duration, thickness=4, start=start)


def test_ripple_progress_bounds():
    r = make_ripple(start=0.0, duration=1.0)
    assert r.progress(0.0) == 0.0
    assert r.progress(0.5) == 0.5
    assert r.progress(1.0) == 1.0
    assert r.progress(2.0) == 1.0  # 1.0 으로 클램프


def test_ripple_expiry():
    r = make_ripple(start=0.0, duration=1.0)
    assert not r.is_expired(0.5)
    assert r.is_expired(1.0)
    assert r.is_expired(1.5)


def test_ripple_radius_grows_and_alpha_fades():
    r = make_ripple(start=0.0, duration=1.0, max_radius=100.0)
    assert r.radius(0.0) == 0.0
    assert r.radius(1.0) == 100.0
    # ease-out: 중간 시점 반지름이 선형(50)보다 큼
    assert r.radius(0.5) > 50.0
    # alpha 는 단조 감소
    assert r.alpha(0.0) == 1.0
    assert r.alpha(0.5) == 0.5
    assert r.alpha(1.0) == 0.0


def test_ripple_zero_duration_is_immediately_done():
    r = make_ripple(start=0.0, duration=0.0)
    assert r.progress(0.0) == 1.0
    assert r.is_expired(0.0)


def test_click_effects_prunes_expired():
    ce = ClickEffects()
    ce.add(make_ripple(start=0.0, duration=1.0))
    ce.add(make_ripple(start=0.0, duration=2.0))
    assert len(ce) == 2
    ce.update(now=1.0)          # 첫 번째 만료
    assert len(ce) == 1
    ce.update(now=2.0)          # 두 번째 만료
    assert len(ce) == 0


def test_click_effects_active_flag():
    ce = ClickEffects()
    assert not ce.active(0.0)
    ce.add(make_ripple(start=0.0, duration=1.0))
    assert ce.active(0.5)
    assert not ce.active(1.0)


def test_laser_trail_prune_removes_old_points():
    t = LaserTrail(lifetime=1.0)
    t.add(0, 0, now=0.0)
    t.add(5, 5, now=0.5)
    assert len(t) == 2
    t.prune(now=1.2)            # 0.0 점은 수명 초과(>1.0)
    assert len(t) == 1


def test_laser_trail_alpha_fades_with_age():
    t = LaserTrail(lifetime=1.0)
    t.add(0, 0, now=0.0)
    pts = t.points_with_alpha(now=0.0)
    assert pts and abs(pts[0][2] - 1.0) < 1e-9
    pts = t.points_with_alpha(now=0.5)
    assert abs(pts[0][2] - 0.5) < 1e-9
    # 수명 초과 점은 alpha<=0 이라 결과에서 제외
    assert t.points_with_alpha(now=1.5) == []


def test_laser_trail_caps_max_points():
    t = LaserTrail(lifetime=10.0, max_points=5)
    for i in range(20):
        t.add(i, i, now=float(i) * 0.001)
    assert len(t) <= 5


def test_laser_trail_same_position_refreshes_only():
    t = LaserTrail(lifetime=1.0)
    t.add(10, 10, now=0.0)
    t.add(10, 10, now=0.3)     # 같은 위치 → 새 점 추가 안 함
    assert len(t) == 1
