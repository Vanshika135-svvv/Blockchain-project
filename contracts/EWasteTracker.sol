// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract EWasteTracker {
    // Structure to record e-waste details on the blockchain
    struct EWaste {
        string id;
        string deviceType;
        uint256 weight;          // In grams or kg (e.g., 2400 for 2.4 kg)
        string status;
        address currentHandler;
        uint256 timestamp;
        bool exists;
    }

    // Mapping from E-Waste ID (e.g., "EW-2026-001") to EWaste struct
    mapping(string => EWaste) private ewasteItems;

    // Events as defined in the project architecture
    event EWasteRegistered(string id, string deviceType, uint256 weight, address indexed handler, uint256 timestamp);
    event EWasteCollected(string id, address indexed handler, uint256 timestamp);
    event EWasteTransferred(string id, address indexed handler, uint256 timestamp);
    event EWasteReceived(string id, address indexed handler, uint256 timestamp);
    event EWasteRecycled(string id, address indexed handler, uint256 timestamp);
    event StatusUpdated(string id, string newStatus, address indexed handler, uint256 timestamp);

    // 1. Register a new E-Waste item
    function registerEWaste(
        string memory _id,
        string memory _deviceType,
        uint256 _weight
    ) public {
        require(!ewasteItems[_id].exists, "E-Waste ID already registered");

        ewasteItems[_id] = EWaste({
            id: _id,
            deviceType: _deviceType,
            weight: _weight,
            status: "REGISTERED",
            currentHandler: msg.sender,
            timestamp: block.timestamp,
            exists: true
        });

        emit EWasteRegistered(_id, _deviceType, _weight, msg.sender, block.timestamp);
    }

    // 2. Accept and mark as Collected (Collection Center)
    function collectEWaste(string memory _id) public {
        require(ewasteItems[_id].exists, "E-Waste ID does not exist");

        ewasteItems[_id].status = "COLLECTED";
        ewasteItems[_id].currentHandler = msg.sender;
        ewasteItems[_id].timestamp = block.timestamp;

        emit EWasteCollected(_id, msg.sender, block.timestamp);
    }

    // 3. Mark as in transit / transferred to transporter
    function transferEWaste(string memory _id) public {
        require(ewasteItems[_id].exists, "E-Waste ID does not exist");

        ewasteItems[_id].status = "IN TRANSIT";
        ewasteItems[_id].currentHandler = msg.sender;
        ewasteItems[_id].timestamp = block.timestamp;

        emit EWasteTransferred(_id, msg.sender, block.timestamp);
    }

    // 4. Recycler receives the e-waste
    function receiveEWaste(string memory _id) public {
        require(ewasteItems[_id].exists, "E-Waste ID does not exist");

        ewasteItems[_id].status = "RECEIVED";
        ewasteItems[_id].currentHandler = msg.sender;
        ewasteItems[_id].timestamp = block.timestamp;

        emit EWasteReceived(_id, msg.sender, block.timestamp);
    }

    // 5. Complete recycling process
    function completeRecycling(string memory _id) public {
        require(ewasteItems[_id].exists, "E-Waste ID does not exist");

        ewasteItems[_id].status = "RECYCLED";
        ewasteItems[_id].currentHandler = msg.sender;
        ewasteItems[_id].timestamp = block.timestamp;

        emit EWasteRecycled(_id, msg.sender, block.timestamp);
    }

    // 6. Generic status updater for custom state transitions
    function updateStatus(string memory _id, string memory _newStatus) public {
        require(ewasteItems[_id].exists, "E-Waste ID does not exist");

        ewasteItems[_id].status = _newStatus;
        ewasteItems[_id].currentHandler = msg.sender;
        ewasteItems[_id].timestamp = block.timestamp;

        emit StatusUpdated(_id, _newStatus, msg.sender, block.timestamp);
    }

    // 7. Retrieve the current on-chain record of an e-waste item
    function getEWaste(string memory _id)
        public
        view
        returns (
            string memory id,
            string memory deviceType,
            uint256 weight,
            string memory status,
            address currentHandler,
            uint256 timestamp
        )
    {
        require(ewasteItems[_id].exists, "E-Waste ID does not exist");
        EWaste memory item = ewasteItems[_id];

        return (
            item.id,
            item.deviceType,
            item.weight,
            item.status,
            item.currentHandler,
            item.timestamp
        );
    }
}