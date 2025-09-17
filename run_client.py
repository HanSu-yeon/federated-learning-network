#!/usr/bin/env python3
"""
연합학습 클라이언트 실행 스크립트
"""
import os
import sys
import re

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """클라이언트를 실행하는 메인 함수"""
    # 환경 변수 확인
    CLIENT_URL = os.environ.get('CLIENT_URL')
    if CLIENT_URL is None:
        print("Error, CLIENT_URL environment variable must be defined.")
        print("Example: export CLIENT_URL='http://127.0.0.1:5003'")
        sys.exit(1)
    
    SERVER_URL = os.environ.get('SERVER_URL')
    if SERVER_URL is None:
        print("Warning: SERVER_URL environment variable is not defined.")
        print("Example: export SERVER_URL='http://localhost:8001'")
    
    # CLIENT_URL에서 포트 추출
    port_match = re.search(r':(\d+)$', CLIENT_URL)
    if port_match:
        port = int(port_match.group(1))
    else:
        port = 5000
    
    # 클라이언트 시작 메시지 출력
    print(f"Starting Federated Learning client on {CLIENT_URL}")
    print(f"Client will listen on port {port}")
    print(f"Server URL: {SERVER_URL or 'Not set'}")
    
    # Flask 앱 실행
    from client.app import app
    app.run(host='0.0.0.0', port=port, debug=True)

if __name__ == '__main__':
    main() 