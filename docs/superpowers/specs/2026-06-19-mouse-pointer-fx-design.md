# Mouse Pointer FX — 설계 문서

작성일: 2026-06-19

## 목적
Windows 로컬 데스크톱에서 동작하는 마우스 포인터 강화 프로그램.
- 커스텀 포인터: 크기 / 모양 / 색 변경
- 클릭 애니메이션 효과
- 레이저 포인터(파워포인트 빨간 레이저 스타일, 단축키 토글)

## 확정 결정
- 기술: **Python 3 + PyQt6**, 전역 입력 후킹 **pynput**, Win32 호출 **pywin32/ctypes**, 패키징 **PyInstaller**.
- 포인터 방식: **투명·항상위·클릭통과 오버레이**에 직접 그림. 커스텀 포인터 사용 시 시스템 커서를 숨김(종료 시 복원 보장).
- 레이저: 기본 단축키 `Ctrl+Alt+L` 토글. 빨간 점 + 페이드 트레일.
- 기본 포인터 스타일 = **파워포인트형 레이저 점**(중심이 밝고 빨간 글로우가 번지는 점). 색/크기/글로우 변경 가능.
- 배포: 트레이 아이콘 + 설정창 포함 단일 `.exe` 빌드.

## 모듈 구성
```
src/mousepointerfx/
  config.py          JSON 설정 로드/저장 + 기본값 (순수 로직, 테스트 대상)
  effects.py         클릭 리플 / 레이저 트레일 수명·기하 계산 (순수 로직, 테스트 대상)
  cursor_renderer.py 포인터 모양 그리기 (QPainter)
  win_cursor.py      시스템 커서 숨김/복원 (ctypes)
  input_hook.py      전역 클릭/단축키 후킹 → Qt 시그널 브리지 (pynput)
  overlay.py         투명·클릭통과 풀스크린 오버레이 창
  settings_window.py 설정 UI (탭: 포인터/클릭/레이저/일반)
  app.py             조립 + 트레이 아이콘 + 생명주기/정리
run.py               진입점
tests/               config / effects 단위 테스트
build.bat            PyInstaller 빌드
```

## 핵심 기술 포인트
- **DPI**: 프로세스를 Per-Monitor-V2 DPI aware로 설정하고, Qt 스케일링을 1로 고정(`QT_ENABLE_HIGHDPI_SCALING=0`, `QT_SCALE_FACTOR=1`)하여 `GetCursorPos`(물리 픽셀)와 Qt 좌표를 1:1로 맞춘다. → 다중 모니터/고배율에서도 포인터 정합.
- **클릭 통과**: Qt `WA_TransparentForMouseEvents` + Win32 `WS_EX_TRANSPARENT|WS_EX_LAYERED|WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE`.
- **오버레이 영역**: 가상 데스크톱 전체(SM_*VIRTUALSCREEN).
- **갱신**: QTimer(~120fps)로 커서위치 폴링 + 효과 진행 + dirty-rect 부분 업데이트로 부하 최소화.
- **커서 숨김/복원**: 숨김은 `SetSystemCursor`(빈 커서), 복원은 `SystemParametersInfo(SPI_SETCURSORS)`. atexit + Qt aboutToQuit + signal + try/finally로 어떤 종료 경로에서도 복원.

## 기본 설정값(요지)
- pointer: enabled, style=`laser`, color=`#FF2D2D`, size=28, glow=on
- click: enabled, style=`ripple`, left=`#3DA5FF`, right=`#FF9B3D`, size=60, duration=450ms
- laser: hotkey=`<ctrl>+<alt>+l`, color=`#FF2D2D`, dot_size=18, trail=on, trail_length=350ms
- general: hide_system_cursor=on, start_with_windows=off

## 에러 처리 / 엣지 케이스
- 시스템 커서 복원 보장(최우선).
- config 손상 → 기본값 폴백 + 재저장.
- 중복 실행 방지(뮤텍스).
- 관리자권한 앱 위에서는 후킹/오버레이가 제한될 수 있음(문서 명시).

## 테스트 전략
- 단위(pytest): config 병합/저장/로드, 리플 진행도·소멸, 레이저 트레일 페이드·prune.
- 수동 체크리스트: 클릭 통과, 다중 모니터 추적, 종료 후 커서 복원, 단축키 토글, 설정 실시간 반영.
