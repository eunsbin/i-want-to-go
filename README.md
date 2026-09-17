# i-want-to-go

> 콘서트에 미친 자가 만든 매크로에 안 걸리는 클릭 스크립트

| 스크립트 | 대상 | 서버 시각 API |
|---|---|---|
| `fans-click.py` | FANS (app.fans) | `time.app.fans/` → `{"epochMs":...}` |
| `nol-click.py` | NOL 티켓 | `api-ticketfront.interpark.com/v1/getServerTime`|

## Prerequisite

접근성 권한 허용 필요

```
시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용
→ 실행할 터미널 앱(Terminal / iTerm / Cursor) 토글 ON
```


## Run

목표 시각은 `"YYYY-MM-DD HH:MM:SS"` 형식, **KST 기준**

```bash
# NOL 티켓 / 인터파크
python3 nol-click.py "2026-09-21 20:00:00"

# FANS
python3 fans-click.py "2026-08-09 20:00:00"
```

1. 예매 버튼 위에 마우스 커서를 올려둔다
2. 커서를 그대로 둔 채 위 명령을 실행한다 — 실행 순간의 좌표가 캡처된다
3. 발사까지 마우스를 움직이지 말고 Mac을 건드리지 않는다
4. 2~4분 전 실행을 권장
