// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

contract AccessManage {
    enum RequestStatus {PENDING, APPROVED, DENIED, EXPIRED }

    struct AccessRequest {
        string requesterName; // 요청자 이름 또는 회사명
        address requester; // 요청자의 지갑 주소
        string dataType; // 요청 대상 데이터 종류 (예: 수면 데이터, 심박수 등)
        address dataOwner; // 데이터 소유자의 주소
        string purpose; // 데이터 요청 목적 (예: AI 분석용 등)
        uint256 requestTime; // 요청 시간 (timestamp)
        uint256 duration; // 요청 유효 시간 (초)
        RequestStatus status; // 현재 요청 상태
    }

    uint256 private requestCounter; // 요청 ID 증가 카운터

    mapping(uint256 => AccessRequest) public accessRequest;  // 요청 ID → 요청 정보
    mapping(address => uint256[]) public userRequests; // 데이터 소유자 주소 → 요청 ID 목록
    mapping(address => uint256[]) public providerRequests; // 요청자 주소 → 요청 ID 목록
    
     //데이터 접근 요청시 발생하는 이벤트
    event AccessRequested(
        uint256 indexed requestId,
        address indexed dataOwner,
        string requesterName,
        address indexed requester,
        string dataType,
        string purpose,
        uint256 duration
    );
    event DataRequested(uint256 indexed requestId, address requester);   //데이터 요청시 발생하는 이벤트
    event RequestApproved(uint256 indexed requestId, address dataOwner, address requester); //승인할때 발생하는 이벤트
    event RequestDenied(uint256 indexed requestId, address dataOwner, address requester); //거부할때 발생하는 이벤트
    event AccessExpired(uint256 indexed requestId, string reason, address requester); //접근 만료시 발생하는 이벤트

     //데이터 접근 요청 
    function requestAccess(
        string memory _requesterName,
        address _dataOwner,
        string memory _dataType,
        string memory _purpose,
        uint256 _duration
    ) public returns (uint256) {
        uint256 requestId = requestCounter++;

        AccessRequest memory request = AccessRequest({
            requesterName: _requesterName,
            requester: msg.sender,
            dataType: _dataType,
            dataOwner: _dataOwner,
            purpose: _purpose,
            requestTime: block.timestamp,
            duration: _duration,
            status: RequestStatus.PENDING
        });

        accessRequest[requestId] = request;
        userRequests[_dataOwner].push(requestId);
        providerRequests[msg.sender].push(requestId);

        emit AccessRequested(
            requestId,
            _dataOwner,
            _requesterName,
            msg.sender,
            _dataType,
            _purpose,
            _duration
        );

        return requestId;
    }


    //여러 건 요청하기
    function batchRequestAccess(
        string[] memory _requesterNames,
        address[] memory _dataOwners,
        string[] memory _dataTypes,
        string[] memory _purposes,
        uint256[] memory _durations
    )public returns (uint256[] memory){
        require(
        _requesterNames.length == _dataOwners.length &&
        _dataOwners.length == _dataTypes.length &&
        _dataTypes.length == _purposes.length &&
        _purposes.length == _durations.length,
        "Input array lengths mismatch"
        );

        uint256[] memory newRequestIds = new uint256[](_requesterNames.length);

        for (uint256 i = 0; i < _requesterNames.length; i++) {
            uint256 requestId = requestCounter++;

            AccessRequest memory request = AccessRequest({
                requesterName : _requesterNames[i],
                requester: msg.sender,
                dataType:_dataTypes[i],
                dataOwner: _dataOwners[i],
                purpose: _purposes[i],
                requestTime : block.timestamp,
                duration: _durations[i],
                status:RequestStatus.PENDING
            });

            accessRequest[requestId] = request;
            userRequests[_dataOwners[i]].push(requestId);
            providerRequests[msg.sender].push(requestId);

            emit AccessRequested(
                requestId,
                _dataOwners[i],
                _requesterNames[i],
                msg.sender,
                _dataTypes[i],
                _purposes[i],
                _durations[i]
            );

            newRequestIds[i] = requestId;
        }
        return newRequestIds;
    }


    //요청 승인(데이터 소유자만 호출 가능)
    function approveReq(uint256 _requestId) public {
        AccessRequest storage request = accessRequest[_requestId];
        require(msg.sender == request.dataOwner, "Not authorized");
        require(request.status == RequestStatus.PENDING, "Request not pending");
        
        request.status = RequestStatus.APPROVED;
        emit RequestApproved(_requestId, request.dataOwner, request.requester);
    }
    //요청 거부(데이터 소유자만 호출 가능)
    function denyReq(uint256 _requestId) public {
        AccessRequest storage request = accessRequest[_requestId];
        require(msg.sender == request.dataOwner, "Not authorized");
        require(request.status == RequestStatus.PENDING, "Request not pending");

        request.status = RequestStatus.DENIED;
        emit RequestDenied(_requestId, request.dataOwner, request.requester);
    }

    //요청 상태 확인 함수
    function checkRequestStatus(uint256 _requestId) public view returns (string memory) {
        RequestStatus status = accessRequest[_requestId].status;
        return statusToString(status);
    }
    //데이터 요청시 실행하는 함수
    function requestData(uint256 _requestId) public {
        AccessRequest storage request = accessRequest[_requestId];
        require(msg.sender == request.requester, "Not authorized");

        if ( block.timestamp > request.requestTime + request.duration) {
            expireAccess(_requestId); // 만료 처리 분리된 함수 호출
            return;
        }

        require(request.status == RequestStatus.APPROVED, "Request not approved");

        emit DataRequested(_requestId, msg.sender);
    }
    function expireAccess(uint256 _requestId) internal {
        AccessRequest storage request = accessRequest[_requestId];
        request.status = RequestStatus.EXPIRED;
        emit AccessExpired(_requestId, "Access token expired", request.requester);
    }


    //사용자 데이터 요청 목록 조회
    function getUserRequests(address _user) public view returns (uint256[] memory) {
        return userRequests[_user];
    }
    //제공자의 요청 목록 조회
    function getProviderRequests(address _provider) public view returns (uint256[] memory) {
        return providerRequests[_provider];
    }

    //사용자 데이터 요청 목록 조회
    function getUserRequestsDetail(address _user) public view returns (
        string[] memory requesterNames,
        address[] memory requesters,
        string[] memory dataTypes,
        address[] memory dataOwners,
        string[] memory purposes,
        uint256[] memory requestTimes,
        uint256[] memory durations,
        string[] memory statuses
    ){
    uint256[] memory requestIds = userRequests[_user];
    uint256 length = requestIds.length;

    requesterNames = new string[](length);
    requesters = new address[](length);
    dataTypes = new string[](length);
    dataOwners = new address[](length);
    purposes = new string[](length);
    requestTimes = new uint256[](length);
    durations = new uint256[](length);
    statuses = new string[](length);

    for (uint256 i = 0; i < length; i++) {
        AccessRequest memory request = accessRequest[requestIds[i]];

        requesterNames[i] = request.requesterName;
        requesters[i] = request.requester;
        dataTypes[i] = request.dataType;
        dataOwners[i] = request.dataOwner;
        purposes[i] = request.purpose;
        requestTimes[i] = request.requestTime;
        durations[i] = request.duration;
        statuses[i] = statusToString(request.status);
    }
}
    
    //건 별 데이터 사용 이력 상세 조회
    function getRequestDetails(uint256 _requestId)
        public
        view
        returns (
            string memory,
            address,
            string memory,
            address,
            string memory,
            uint256,
            uint256,
            string memory
        )
    {
        AccessRequest memory request = accessRequest[_requestId];
        return (
            request.requesterName,
            request.requester,
            request.dataType,
            request.dataOwner,
            request.purpose,
            request.requestTime,
            request.duration,
            statusToString(request.status)
        );
    }
    function getPendingRequestCount(address _owner) external view returns (uint256) {
        uint256 count = 0;
        uint256[] memory ids = userRequests[_owner];
        for (uint i = 0; i < ids.length; i++) {
            if (accessRequest[ids[i]].status == RequestStatus.PENDING) {
                count++;
            }
        }
        return count;
    }
    

    // 요청 상태(enum)를 사람이 읽을 수 있는 문자열로 변환
    function statusToString(RequestStatus status) internal pure returns (string memory) {
        if (status == RequestStatus.PENDING) return "PENDING";
        if (status == RequestStatus.APPROVED) return "APPROVED";
        if (status == RequestStatus.DENIED) return "DENIED";
        if (status == RequestStatus.EXPIRED) return "EXPIRED";
        return "UNKNOWN";
    }
}
