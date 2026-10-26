import os
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from web3 import Web3
import qrcode
import base64
from io import BytesIO
import time
import datetime

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# 1. MongoDB Setup using .env
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
client = MongoClient(MONGO_URI)
db = client["ecochain"]
ewaste_collection = db["ewaste"]

# 2. Blockchain Setup
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
default_account = w3.eth.accounts[0]
w3.eth.default_account = default_account

# Contract Address loaded from .env
contract_address = os.getenv("CONTRACT_ADDRESS", "0x5FbDB2315678afecb367f032d93F642f64180aa3")

# Full ABI for EWasteTracker.sol
contract_abi = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "string", "name": "id", "type": "string"},
            {"indexed": True, "internalType": "address", "name": "handler", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "EWasteCollected",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "string", "name": "id", "type": "string"},
            {"indexed": True, "internalType": "address", "name": "handler", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "EWasteReceived",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "string", "name": "id", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "deviceType", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "weight", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "handler", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "EWasteRecycled",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "string", "name": "id", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "deviceType", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "weight", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "handler", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "EWasteRegistered",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "string", "name": "id", "type": "string"},
            {"indexed": True, "internalType": "address", "name": "handler", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "EWasteTransferred",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "string", "name": "id", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "newStatus", "type": "string"},
            {"indexed": True, "internalType": "address", "name": "handler", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "StatusUpdated",
        "type": "event"
    },
    {
        "inputs": [{"internalType": "string", "name": "_id", "type": "string"}],
        "name": "collectEWaste",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "_id", "type": "string"}],
        "name": "completeRecycling",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "_id", "type": "string"}],
        "name": "getEWaste",
        "outputs": [
            {"internalType": "string", "name": "id", "type": "string"},
            {"internalType": "string", "name": "deviceType", "type": "string"},
            {"internalType": "uint256", "name": "weight", "type": "uint256"},
            {"internalType": "string", "name": "status", "type": "string"},
            {"internalType": "address", "name": "currentHandler", "type": "address"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "_id", "type": "string"}],
        "name": "receiveEWaste",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "_id", "type": "string"},
            {"internalType": "string", "name": "_deviceType", "type": "string"},
            {"internalType": "uint256", "name": "_weight", "type": "uint256"}
        ],
        "name": "registerEWaste",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "_id", "type": "string"}],
        "name": "transferEWaste",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "_id", "type": "string"},
            {"internalType": "string", "name": "_newStatus", "type": "string"}
        ],
        "name": "updateStatus",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

contract = w3.eth.contract(address=contract_address, abi=contract_abi)

# ---------------- API ROUTES ----------------

@app.route('/api/ewaste/register', methods=['POST'])
def register_ewaste():
    try:
        data = request.json
        ewaste_id = f"EW-{int(time.time())}"
        device_type = data.get('deviceType', 'Electronic Device')
        weight_kg = float(data.get('weight', 1.0))
        weight_grams = int(weight_kg * 1000)

        # Execute on local Hardhat blockchain
        tx_hash = contract.functions.registerEWaste(ewaste_id, device_type, weight_grams).transact()
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        blockchain_hash = receipt.transactionHash.hex()

        # QR code pointing to tracking timeline
        qr_url = f"http://127.0.0.1:5500/track.html?id={ewaste_id}"
        qr = qrcode.make(qr_url)
        buffered = BytesIO()
        qr.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        qr_data_url = f"data:image/png;base64,{qr_base64}"

        new_item = {
            "ewasteId": ewaste_id,
            "ownerName": data.get('ownerName', 'Anonymous'),
            "deviceType": device_type,
            "weight": weight_kg,
            "condition": data.get('condition', 'Used'),
            "status": "REGISTERED",
            "qrCodeDataURL": qr_data_url,
            "transactionHashes": [{
                "status": "REGISTERED",
                "hash": blockchain_hash,
                "handler": default_account,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }]
        }
        ewaste_collection.insert_one(new_item)
        new_item['_id'] = str(new_item['_id'])

        return jsonify({"success": True, "item": new_item}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ewaste/update', methods=['POST'])
def update_ewaste():
    try:
        data = request.json
        ewaste_id = data.get('ewasteId')
        new_status = data.get('status')

        if new_status == "COLLECTED":
            tx_hash = contract.functions.collectEWaste(ewaste_id).transact()
        elif new_status == "IN TRANSIT":
            tx_hash = contract.functions.transferEWaste(ewaste_id).transact()
        elif new_status == "RECEIVED":
            tx_hash = contract.functions.receiveEWaste(ewaste_id).transact()
        elif new_status == "RECYCLED":
            tx_hash = contract.functions.completeRecycling(ewaste_id).transact()
        else:
            tx_hash = contract.functions.updateStatus(ewaste_id, new_status).transact()

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        blockchain_hash = receipt.transactionHash.hex()

        ewaste_collection.update_one(
            {"ewasteId": ewaste_id},
            {
                "$set": {"status": new_status},
                "$push": {
                    "transactionHashes": {
                        "status": new_status,
                        "hash": blockchain_hash,
                        "handler": default_account,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                }
            }
        )

        return jsonify({"success": True, "status": new_status, "txHash": blockchain_hash}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ewaste/<ewaste_id>', methods=['GET'])
def get_ewaste_details(ewaste_id):
    try:
        item = ewaste_collection.find_one({"ewasteId": ewaste_id})
        if not item:
            return jsonify({"success": False, "message": "E-Waste ID not found"}), 404

        item['_id'] = str(item['_id'])
        return jsonify({"success": True, "item": item}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ewaste/all', methods=['GET'])
def get_all_ewaste():
    try:
        items = list(ewaste_collection.find())
        for doc in items:
            doc['_id'] = str(doc['_id'])
        return jsonify({"success": True, "items": items}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    app.run(port=5000, debug=True)