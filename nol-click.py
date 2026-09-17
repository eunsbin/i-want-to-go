#!/usr/bin/env python3
"""
1. api-ticketfront.interpark.com/v1/getServerTime으로 서버 시각 확인 (NOL 티켓 예매 기준)
2. 목표 :00 직전까지 폴링 후 로컬 타이머로 정확히 :00에 클릭
3. CoreGraphics로 직접 마우스 이벤트

사용법:
  python3 nol-click.py "2026-09-21 20:00:00"

실행 시점의 마우스 커서 위치에 클릭합니다. 미러링 창 위에 커서를 올려둔 뒤 실행하세요.

사전 준비:
  시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용
  → 실행하는 터미널 앱(Terminal / Cursor) 허용
"""

from __future__ import annotations

import ctypes
import ctypes.util
import gc
import http.client
import ssl
import sys
import time
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# nol.yanolja.com 예매 버튼 → tickets.interpark.com/gates/partner (GATE_PAGE_ORIGIN)
# 게이트 페이지가 카운트다운에 쓰는 BFF 서버 시각 API
TIME_HOST = "api-ticketfront.interpark.com"
TIME_PATH = "/v1/getServerTime?type=1&nc="  # nc = 캐시 버스터(Date.now())
TIME_HEADERS = {
    "Referer": "https://tickets.interpark.com/",
    "Origin": "https://tickets.interpark.com",
    "Accept": "*/*",
    "Cache-Control": "no-store",
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
}


# ---------------------------------------------------------------- 클릭 (CoreGraphics)

class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


def _load_cg():
    cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
    cg.CGEventCreate.restype = ctypes.c_void_p
    cg.CGEventCreate.argtypes = [ctypes.c_void_p]
    cg.CGEventGetLocation.restype = CGPoint
    cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]
    cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
    cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    cg.CGEventPost.restype = None
    return cg


def current_mouse_pos() -> tuple[int, int]:
    cg = _load_cg()
    cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
    cf.CFRelease.argtypes = [ctypes.c_void_p]

    event = cg.CGEventCreate(None)
    pt = cg.CGEventGetLocation(event)
    cf.CFRelease(event)
    return int(pt.x), int(pt.y)


def make_click(x: int, y: int):
    cg = _load_cg()

    pt = CGPoint(float(x), float(y))
    down = cg.CGEventCreateMouseEvent(None, 1, pt, 0)  # kCGEventLeftMouseDown
    up = cg.CGEventCreateMouseEvent(None, 2, pt, 0)    # kCGEventLeftMouseUp

    def fire() -> None:
        cg.CGEventPost(0, down)
        cg.CGEventPost(0, up)

    return fire


# ---------------------------------------------------------------- 서버 시간 (interpark BFF)

def open_conn() -> http.client.HTTPSConnection:
    conn = http.client.HTTPSConnection(TIME_HOST, timeout=3, context=ssl.create_default_context())
    fetch_epoch_ms(conn)  # TLS 핸드셰이크 미리 끝내두기 (첫 요청만 RTT ~50ms)
    return conn


def fetch_epoch_ms(conn: http.client.HTTPSConnection) -> tuple[int, float, float]:
    """(epochMs, 요청 송신 시각, 왕복 시간)"""
    t0 = time.monotonic()
    conn.request("GET", TIME_PATH + str(int(time.time() * 1000)), headers=TIME_HEADERS)
    res = conn.getresponse()
    body = res.read()
    t1 = time.monotonic()
    epoch_ms = int(body.strip())  # 응답은 epoch ms 숫자 텍스트
    return epoch_ms, t0, t1 - t0


def server_offset(epoch_ms: int, t0: float, rtt: float) -> float:
    """monotonic + offset ≈ 인터파크 서버 시각(초)

    게이트 페이지도 USE_LATENCY_COMPENSATION=false로 응답 도착 시점을
    서버 시각으로 삼으므로 동일하게 맞춘다.
    """
    return epoch_ms / 1000.0 - (t0 + rtt)


def wait_until_near_target(conn: http.client.HTTPSConnection, target_ts: float) -> float:
    """서버 시각을 폴링하다 목표 :00 직전(100ms)에 offset 반환."""
    target_ms = int(target_ts * 1000)
    last_print = 0.0

    while True:
        epoch_ms, t0, rtt = fetch_epoch_ms(conn)
        remain_ms = target_ms - epoch_ms
        now = time.monotonic()

        if remain_ms < -500:
            print("목표 시각이 이미 지났습니다.")
            sys.exit(1)
        if remain_ms <= 100:
            print(f"[동기화] {remain_ms / 1000:.3f}초 남음 → 로컬 타이머로 :00 클릭", flush=True)
            return server_offset(epoch_ms, t0, rtt)

        if remain_ms <= 1000 or now - last_print >= 0.5:
            server_str = datetime.fromtimestamp(epoch_ms / 1000, KST).strftime("%H:%M:%S.%f")[:-3]
            print(f"[폴링] {remain_ms / 1000:.2f}초 남음  서버 {server_str}  rtt {rtt * 1000:.0f}ms", flush=True)
            last_print = now

        if remain_ms > 5000:
            time.sleep(min(1.0, (remain_ms - 3000) / 1000))
        elif remain_ms > 1000:
            time.sleep(0.1)
        # 1000ms ~ 100ms: sleep 없이 연속 요청 (RTT ~10–20ms마다 1회)


# ---------------------------------------------------------------- 메인

def parse_args(argv: list[str]) -> str:
    if len(argv) < 2:
        print(__doc__)
        sys.exit(1)
    return argv[1]


def spin_until_mono(deadline: float) -> None:
    while True:
        remain = deadline - time.monotonic()
        if remain <= 0:
            return
        if remain > 0.05:
            time.sleep(remain - 0.03)
        else:
            while time.monotonic() < deadline:
                pass
            return


def main() -> None:
    target_str = parse_args(sys.argv)
    x, y = current_mouse_pos()
    target_ts = datetime.strptime(target_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST).timestamp()

    fire = make_click(x, y)
    conn = open_conn()

    epoch_ms, _, _ = fetch_epoch_ms(conn)
    remain = (int(target_ts * 1000) - epoch_ms) / 1000
    if remain < 1:
        print("목표까지 1초 미만입니다. 더 일찍 실행하세요.")
        sys.exit(1)

    print(f"목표까지 {remain:.1f}초. ({x}, {y}) 인터파크 서버 :00에 클릭.")
    print("미러링 창을 움직이지 말고 Mac을 건드리지 마세요.")

    offset = wait_until_near_target(conn, target_ts)
    conn.close()

    deadline = target_ts - offset

    gc.disable()
    print("[클릭] :00 발사", flush=True)
    spin_until_mono(deadline)
    fire()
    gc.enable()

    print(f"클릭 완료: {datetime.now(KST).strftime('%H:%M:%S.%f')[:-3]} "
          f"(서버 기준 약 {(time.monotonic() + offset - target_ts) * 1000:+.0f}ms)")


if __name__ == "__main__":
    main()
