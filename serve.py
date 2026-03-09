"""
로컬 대시보드 서버
사용법: uv run python serve.py [포트번호]  (기본값: 8000)
"""

import http.server
import os
import sys
import webbrowser
from pathlib import Path


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    dashboard_dir = Path(__file__).parent / "dashboard"
    os.chdir(dashboard_dir)

    url = f"http://localhost:{port}"
    print(f"대시보드 서버 시작: {url}")
    print("종료하려면 Ctrl+C 를 누르세요.")
    webbrowser.open(url)

    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *args: None  # 로그 비활성화
    with http.server.HTTPServer(("", port), handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
