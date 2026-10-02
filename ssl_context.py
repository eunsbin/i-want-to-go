"""HTTPS: macOS Keychain 등 OS 신뢰 저장소(truststore)."""

from __future__ import annotations

import ssl
import sys

_SSL_HINT = """\
SSL 인증 실패. Homebrew Python 등은 CA 번들이 curl/Safari와 달라 실패할 수 있습니다.
회사망 SSL 검사 환경이면 특히 그렇습니다. venv에 truststore를 설치하세요:

  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  python nol-click.py "YYYY-MM-DD HH:MM:SS"
"""


def ssl_context() -> ssl.SSLContext:
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


def die_on_ssl_verify_error(exc: BaseException) -> None:
    if isinstance(exc, ssl.SSLCertVerificationError):
        print(_SSL_HINT, file=sys.stderr)
        sys.exit(1)
    raise exc
