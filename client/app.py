import os
import signal

from flask import Flask, request, Response, jsonify
from os import environ

from .client import Client
from .federated_learning_config import FederatedLearningConfig
from .utils import request_params_to_model_params, model_params_to_request_params
from .training_type import TrainingType

CLIENT_URL = environ.get('CLIENT_URL')
if CLIENT_URL is None:
    print("Error, CLIENT_URL environment variable must be defined. "
          "Example: export CLIENT_URL='http://127.0.0.1:5003' if client is running on port 5003")
    os.kill(os.getpid(), signal.SIGINT)

app = Flask(__name__)
client = Client(CLIENT_URL)


@app.route('/')
def index():
    return 'Federated Learning client running. Status: ' + client.status


@app.route('/training', methods=['POST'])
def training():
    training_type = request.json['training_type']
    print('Request POST /training for training type:', training_type)
    federated_learning_config = FederatedLearningConfig(request.json['learning_rate'],
                                                        request.json['epochs'],
                                                        request.json['batch_size'])
    model_params = request_params_to_model_params(training_type, request.json)
    client_id = request.json['client_id']
    round = request.json['round']
    # round_size = request.json['round_size']
     # round_size에 기본값 설정 (에러 방지)
    round_size = request.json.get('round_size', 1)
    clients = request.json.get('clients', None)
    client.do_training(training_type, model_params, federated_learning_config, client_id, round, round_size, clients)
    return Response(status=200)


@app.route('/model_params', methods=['GET'])
def get_model_params():
    model_params = model_params_to_request_params(TrainingType.GOSSIP_MNIST, client.model_params)
    response = jsonify({'model_params': model_params})
    response.status_code = 200
    return response


@app.errorhandler(404)
def page_not_found(error):
    return 'This page does not exist', 404


# ============================================
# 클라이언트 실행을 위한 메인 실행 코드
# ============================================
if __name__ == '__main__':
    # CLIENT_URL 환경 변수에서 포트 번호를 추출하는 정규표현식
    import re
    port_match = re.search(r':(\d+)$', CLIENT_URL)
    
    if port_match:
        # URL에서 포트 번호를 추출 (예: http://127.0.0.1:5003 -> 5003)
        port = int(port_match.group(1))
    else:
        # 포트가 명시되지 않은 경우 기본 포트 사용
        port = 5000
    
    # 클라이언트 서버 시작 메시지 출력
    print(f"Starting Federated Learning client on {CLIENT_URL}")
    print(f"Client will listen on port {port}")
    print(f"Server URL: {environ.get('SERVER_URL', 'Not set')}")
    
    # Flask 앱을 지정된 포트에서 실행
    # host='0.0.0.0': 모든 네트워크 인터페이스에서 접근 가능
    # debug=True: 개발 모드로 실행 (코드 변경 시 자동 재시작)
    app.run(host='0.0.0.0', port=port, debug=True)
