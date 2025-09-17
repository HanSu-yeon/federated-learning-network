import asyncio
import sys
import aiohttp
import torch

import numpy as np

# 필요한 모듈들 임포트
from .utils import model_params_to_request_params
from .federated_learning_config import FederatedLearningConfig
from .client_training_status import ClientTrainingStatus
from .server_status import ServerStatus
from .training_client import TrainingClient
from .training_type import TrainingType


class Server:
    """
    연합학습을 관리하는 중앙 서버 클래스
    - MNIST와 Chest X-Ray 데이터셋에 대한 연합학습을 지원
    - 여러 클라이언트의 학습을 조율하고 모델 파라미터를 집계
    """
    def __init__(self):
        # MNIST 모델의 파라미터 (weights, bias)
        self.mnist_model_params = None
        # Chest X-Ray 모델의 파라미터
        self.chest_x_ray_model_params = None
        # 초기 모델 파라미터 생성
        self.init_params()
        # 연결된 클라이언트들을 관리하는 딕셔너리
        self.training_clients = {}
        # 서버의 현재 상태 (IDLE, CLIENTS_TRAINING 등)
        self.status = ServerStatus.IDLE
        # 현재 학습 라운드 번호
        self.round = 0

    def init_params(self):
        """
        MNIST 모델의 초기 파라미터를 생성하는 메서드
        - 28*28=784 크기의 입력에 대한 가중치와 편향을 무작위로 초기화
        - requires_grad=True로 설정하여 역전파 시 gradient 계산 가능
        """
        if self.mnist_model_params is None:
            # 입력 크기(784)에서 출력 크기(1)로 가는 가중치 행렬
            weights = torch.randn((28 * 28, 1), dtype=torch.float, requires_grad=True)
            # 편향(bias) 벡터
            bias = torch.randn(1, dtype=torch.float, requires_grad=True)
            self.mnist_model_params = weights, bias

    async def start_training(self, training_type):
        """
        연합학습 라운드를 시작하는 비동기 메서드
        - 서버의 상태와 클라이언트 연결 상태를 확인
        - 학습 타입에 따라 다른 설정으로 클라이언트들에게 학습 요청
        """
        if self.status != ServerStatus.IDLE:
            print('Server is not ready for training yet, status:', self.status)
            for training_client in self.training_clients.values():
                print(training_client)
        elif len(self.training_clients) == 0:
            print("There aren't any clients registered in the system, nothing to do yet")
        else:
            # 학습 라운드 증가 (deterministic MNIST 학습에 필요)
            self.round += 1

            request_body = {}
            federated_learning_config = None
            if (
                    training_type == TrainingType.MNIST
                    or training_type == TrainingType.DETERMINISTIC_MNIST
            ):
                request_body = model_params_to_request_params(training_type, self.mnist_model_params)
                federated_learning_config = FederatedLearningConfig(learning_rate=1., epochs=20, batch_size=256)
            elif training_type == TrainingType.GOSSIP_MNIST:
                request_body = model_params_to_request_params(training_type, None)
                federated_learning_config = FederatedLearningConfig(learning_rate=1., epochs=20, batch_size=256)
            elif training_type == TrainingType.CHEST_X_RAY_PNEUMONIA:
                request_body = model_params_to_request_params(training_type, self.chest_x_ray_model_params)
                federated_learning_config = FederatedLearningConfig(learning_rate=0.0001, epochs=1, batch_size=2)

            request_body['learning_rate'] = federated_learning_config.learning_rate
            request_body['epochs'] = federated_learning_config.epochs
            request_body['batch_size'] = federated_learning_config.batch_size
            request_body['training_type'] = training_type
            request_body['round'] = self.round

            if training_type == TrainingType.GOSSIP_MNIST:
                # Send all client urls and ids to each client for decentralized learning
                clients = [
                    {"client_id": client.client_id, "client_url": client.client_url}
                    for client in self.training_clients.values()
                ]
                request_body['clients'] = clients

            print('There are', len(self.training_clients), 'clients registered')
            tasks = []
            for training_client in self.training_clients.values():
                if training_type == TrainingType.DETERMINISTIC_MNIST or training_type == TrainingType.GOSSIP_MNIST:
                    request_body['round_size'] = len(self.training_clients.values())
                tasks.append(
                    asyncio.ensure_future(self.do_training_client_request(training_type, training_client, request_body))
                )
            print('Requesting training to clients...')
            self.status = ServerStatus.CLIENTS_TRAINING
            await asyncio.gather(*tasks)
        sys.stdout.flush()

    async def do_training_client_request(self, training_type, training_client, request_body):
        request_url = training_client.client_url + '/training'
        print('Requesting training to client', request_url)
        async with aiohttp.ClientSession() as session:
            # Ensures individual client_ids are sent to each client
            request_body['client_id'] = training_client.client_id
            training_client.status = ClientTrainingStatus.TRAINING_REQUESTED
            async with session.post(request_url, json=request_body) as response:
                if response.status != 200:
                    print('Error requesting training to client', training_client.client_url)
                    training_client.status = ClientTrainingStatus.TRAINING_REQUEST_ERROR
                    self.update_server_model_params(training_type)
                else:
                    print('Client', training_client.client_url, 'started training')

    def update_client_model_params(self, training_type, training_client, client_model_params):
        """
        클라이언트로부터 받은 모델 파라미터를 업데이트하는 메서드
        - 클라이언트의 학습 결과(파라미터)를 저장
        - 클라이언트의 상태를 TRAINING_FINISHED로 변경
        - 서버의 글로벌 모델 파라미터 업데이트를 시도
        """
        print('New model params received from client', training_client.client_url)
        training_client.model_params = client_model_params
        training_client.status = ClientTrainingStatus.TRAINING_FINISHED
        self.update_server_model_params(training_type)

    # Forces the round to finish. This is used for Gossip training
    # since no parameters will be sent back to the server
    # so the server needs to know when the round is finished
    def finish_round(self, training_type, training_client):
        training_client.status = ClientTrainingStatus.TRAINING_FINISHED

        if self.can_update_central_model_params() and training_type == TrainingType.GOSSIP_MNIST:
            self.status = ServerStatus.IDLE
            for training_client in self.training_clients.values():
                training_client.status = ClientTrainingStatus.IDLE
        sys.stdout.flush()

    def update_server_model_params(self, training_type):
        """
        서버의 글로벌 모델 파라미터를 업데이트하는 메서드
        - 모든 클라이언트의 학습이 완료되었는지 확인
        - 각 클라이언트의 모델 파라미터를 수집하여 평균 계산 (FedAvg 알고리즘)
        - MNIST와 Chest X-Ray 모델에 대해 각각 다른 방식으로 처리
        """
        if self.can_update_central_model_params():
            print('Updating global model params')
            self.status = ServerStatus.UPDATING_MODEL_PARAMS
            if training_type == TrainingType.MNIST or training_type == TrainingType.DETERMINISTIC_MNIST:
                received_weights = []
                received_biases = []
                for training_client in self.training_clients.values():
                    if training_client.status == ClientTrainingStatus.TRAINING_FINISHED:
                        received_weights.append(training_client.model_params[0])
                        received_biases.append(training_client.model_params[1])
                        training_client.status = ClientTrainingStatus.IDLE
                new_weights = torch.stack(received_weights).mean(0)
                new_bias = torch.stack(received_biases).mean(0)
                self.mnist_model_params = new_weights, new_bias
                print('Model weights for', training_type, 'updated in central model')
            elif training_type == TrainingType.CHEST_X_RAY_PNEUMONIA:
                received_weights = []
                for training_client in self.training_clients.values():
                    if training_client.status == ClientTrainingStatus.TRAINING_FINISHED:
                        training_client.status = ClientTrainingStatus.IDLE
                        received_weights.append(training_client.model_params)
                new_weights = np.stack(received_weights).mean(0)
                self.chest_x_ray_model_params = new_weights
                print('Model weights for', TrainingType.CHEST_X_RAY_PNEUMONIA, 'updated in central model')
            self.status = ServerStatus.IDLE
        sys.stdout.flush()

    def can_update_central_model_params(self):
        for training_client in self.training_clients.values():
            if training_client.status != ClientTrainingStatus.TRAINING_FINISHED \
                    and training_client.status != ClientTrainingStatus.TRAINING_REQUEST_ERROR:
                return False
        return True

    def register_client(self, client_url):
        print('Registering new training client [', client_url, ']')
        if self.training_clients.get(client_url) is None:
            next_client_id = len(self.training_clients) + 1
            self.training_clients[client_url] = TrainingClient(client_url, next_client_id)
        else:
            print('Client [', client_url, '] was already registered in the system')
            self.training_clients.get(client_url).status = ClientTrainingStatus.IDLE
        sys.stdout.flush()

    def unregister_client(self, client_url):
        print('Unregistering client [', client_url, ']')
        try:
            self.training_clients.pop(client_url)
            print('Client [', client_url, '] unregistered successfully')
        except KeyError:
            print('Client [', client_url, '] is not registered yet')
        sys.stdout.flush()

    def can_do_training(self):
        for training_client in self.training_clients.values():
            if training_client.status != ClientTrainingStatus.IDLE \
                    and training_client.status != ClientTrainingStatus.TRAINING_REQUEST_ERROR:
                return False

        return True

