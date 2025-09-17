#!/usr/bin/env python3
"""
연합학습 서버 실행 스크립트
"""
import os
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import create_app

def main():
    """서버를 실행하는 메인 함수"""
    # 서버 포트 설정 (환경 변수에서 가져오거나 기본값 사용)
    server_port = int(os.environ.get('SERVER_PORT', 5000))
    
    # 서버 시작 메시지 출력
    print(f"Starting Federated Learning server on port {server_port}")
    print("Server will manage federated learning clients and coordinate training")
    
    # Flask 앱을 지정된 포트에서 실행
    # host='0.0.0.0': 모든 네트워크 인터페이스에서 접근 가능
    # debug=True: 개발 모드로 실행 (코드 변경 시 자동 재시작)
    app = create_app()
    app.run(host='0.0.0.0', port=server_port, debug=True)

if __name__ == '__main__':
    main() 