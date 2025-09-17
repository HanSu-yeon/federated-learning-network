import asyncio
import os

from flask import (
    Flask, Response, request, render_template, jsonify
)

# from server import Server
# from training_type import TrainingType
# from utils import request_params_to_model_params
# 상대 임포트를 절대 임포트로 변경
from server.server import Server
from server.training_type import TrainingType
from server.utils import request_params_to_model_params


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    server = Server()

    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'fl-network.sqlite'),
    )
    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route('/')
    def index():
        clients_ready_for_training = server.can_do_training()
        return render_template("index.html",
                               server_status=server.status,
                               training_clients=server.training_clients,
                               clients_ready_for_training=clients_ready_for_training)

    @app.route('/training', methods=['POST'])
    def training():
        training_type = request.json['training_type']
        asyncio.run(server.start_training(training_type))
        return Response(status=200)

    @app.route('/client', methods=['POST'])
    def register_client():
        print('Request POST /client for client_url [', request.form['client_url'], ']')
        server.register_client(request.form['client_url'])
        return Response(status=201)

    @app.route('/client', methods=['DELETE'])
    def unregister_client():
        print('Request DELETE /client for client_url [', request.form['client_url'], ']')
        server.unregister_client(request.form['client_url'])
        return Response(status=200)

    @app.route('/model_params', methods=['PUT'])
    def update_weights():
        client_url = request.json['client_url']
        training_type = request.json['training_type']
        print('Request PUT /model_params for client_url [', client_url, '] and training type:', training_type)
        try:
            training_client = server.training_clients[request.json['client_url']]
            server.update_client_model_params(training_type, training_client, request_params_to_model_params(training_type, request.json))
            return Response(status=200)
        except KeyError:
            print('Client', client_url, 'is not registered in the system')
            return Response(status=401)

    @app.route('/finish_round', methods=['POST'])
    def finish_round():
        client_url = request.json['client_url']
        training_type = request.json['training_type']
        print('Request POST /finish_round for client_url [', client_url, '] and training type:', training_type)
        if training_type == TrainingType.GOSSIP_MNIST:
            training_client = server.training_clients[request.json['client_url']]
            server.finish_round(training_type, training_client)
            return Response(status=200)
        else:
            return Response(status=400)


    @app.errorhandler(404)
    def page_not_found(error):
        return 'This page does not exist', 404

    return app


# ============================================
# 서버 실행을 위한 메인 실행 코드
# ============================================
if __name__ == '__main__':
    # 서버 포트 설정 (환경 변수에서 가져오거나 기본값 사용)
    server_port = int(os.environ.get('SERVER_PORT', 8001))
    
    # 서버 시작 메시지 출력
    print(f"Starting Federated Learning server on port {server_port}")
    print("Server will manage federated learning clients and coordinate training")
    
    # Flask 앱을 지정된 포트에서 실행
    # host='0.0.0.0': 모든 네트워크 인터페이스에서 접근 가능
    # debug=True: 개발 모드로 실행 (코드 변경 시 자동 재시작)
    app = create_app()
    app.run(host='0.0.0.0', port=server_port, debug=True)
