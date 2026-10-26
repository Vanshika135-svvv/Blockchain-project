import base64
import datetime
from io import BytesIO
import os
import secrets
import time
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
import qrcode
from web3 import Web3
from werkzeug.security import check_password_hash, generate_password_hash

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# 1. MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
client = MongoClient(MONGO_URI)
db = client["ecochain"]
ewaste_collection = db["ewaste"]
users_collection = db["users"]

# 2. Blockchain Setup (Supports Hardhat localhost and cloud RPCs like Sepolia)
BLOCKCHAIN_RPC_URL = os.getenv("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:8545")
w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_RPC_URL))

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
if PRIVATE_KEY:
    account = w3.eth.account.from_key(PRIVATE_KEY)
    default_account = account.address
    w3.eth.default_account = default_account
else:
    default_account = w3.eth.accounts[0] if len(w3.eth.accounts) > 0 else None
    w3.eth.default_account = default_account

# Contract Address loaded from environment
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


def send_transaction(func_call):
    """Helper to send transactions handling both local nodes and private-key signing."""
    if PRIVATE_KEY:
        nonce = w3.eth.get_transaction_count(default_account)
        tx = func_call.build_transaction({
            'from': default_account,
            'nonce': nonce,
            'gasPrice': w3.eth.gas_price
        })
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    else:
        tx_hash = func_call.transact({'from': default_account})
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt.transactionHash.hex()


# ---------------- API ROUTES ----------------

# 1. Register new e-waste item
@app.route('/api/ewaste/register', methods=['POST'])
def register_ewaste():
    try:
        data = request.json
        ewaste_id = f"EW-{int(time.time())}"
        device_type = data.get('deviceType', 'Electronic Device')
        weight_kg = float(data.get('weight', 1.0))
        weight_grams = int(weight_kg * 1000)

        # Execute transaction on blockchain
        blockchain_hash = send_transaction(
            contract.functions.registerEWaste(ewaste_id, device_type, weight_grams)
        )

        # Generate QR code for tracking asset
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


# 2. Update status across standard lifecycle stages
@app.route('/api/ewaste/update', methods=['POST'])
def update_ewaste():
    try:
        data = request.json
        ewaste_id = data.get('ewasteId')
        new_status = data.get('status')

        if new_status == "COLLECTED":
            call = contract.functions.collectEWaste(ewaste_id)
        elif new_status == "IN TRANSIT":
            call = contract.functions.transferEWaste(ewaste_id)
        elif new_status == "RECEIVED":
            call = contract.functions.receiveEWaste(ewaste_id)
        elif new_status == "RECYCLED":
            call = contract.functions.completeRecycling(ewaste_id)
        else:
            call = contract.functions.updateStatus(ewaste_id, new_status)

        blockchain_hash = send_transaction(call)

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


# 3. Retrieve item details for track.html timeline
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


# 4. Fetch all records for admin metrics
@app.route('/api/ewaste/all', methods=['GET'])
def get_all_ewaste():
    try:
        items = list(ewaste_collection.find())
        for doc in items:
            doc['_id'] = str(doc['_id'])
        return jsonify({"success": True, "items": items}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 5. Search & Filter endpoint for Explorer dashboard
@app.route('/api/ewaste/search', methods=['GET'])
def search_ewaste():
    try:
        query = request.args.get('q', '').strip()
        status_filter = request.args.get('status', '').strip()

        filter_dict = {}
        if query:
            filter_dict["$or"] = [
                {"ewasteId": {"$regex": query, "$options": "i"}},
                {"ownerName": {"$regex": query, "$options": "i"}},
                {"deviceType": {"$regex": query, "$options": "i"}}
            ]
        if status_filter and status_filter != 'ALL':
            filter_dict["status"] = status_filter

        items = list(ewaste_collection.find(filter_dict))
        for doc in items:
            doc['_id'] = str(doc['_id'])
        return jsonify({"success": True, "items": items}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 6. Recycler Material Breakdown Logger
@app.route('/api/ewaste/recycle-breakdown', methods=['POST'])
def log_recycling_breakdown():
    try:
        data = request.json
        ewaste_id = data.get('ewasteId')
        recovered_materials = data.get('materials', {})

        blockchain_hash = send_transaction(contract.functions.completeRecycling(ewaste_id))

        ewaste_collection.update_one(
            {"ewasteId": ewaste_id},
            {
                "$set": {
                    "status": "RECYCLED",
                    "recoveredMaterials": recovered_materials
                },
                "$push": {
                    "transactionHashes": {
                        "status": "RECYCLED",
                        "hash": blockchain_hash,
                        "handler": default_account,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                }
            }
        )
        return jsonify({"success": True, "txHash": blockchain_hash, "materials": recovered_materials}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 7. Authentication: Sign Up
@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    try:
        data = request.json
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not name or not email or not password:
            return jsonify({"success": False, "error": "All fields are required"}), 400

        if users_collection.find_one({"email": email}):
            return jsonify({"success": False, "error": "An account with this email already exists"}), 400

        user_doc = {
            "name": name,
            "email": email,
            "passwordHash": generate_password_hash(password),
            "createdAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        users_collection.insert_one(user_doc)
        token = secrets.token_hex(24)

        return jsonify({
            "success": True,
            "token": token,
            "user": {"name": name, "email": email}
        }), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 8. Authentication: Log In
@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        user = users_collection.find_one({"email": email})
        if not user or not check_password_hash(user['passwordHash'], password):
            return jsonify({"success": False, "error": "Invalid email or password"}), 401

        token = secrets.token_hex(24)
        return jsonify({
            "success": True,
            "token": token,
            "user": {"name": user['name'], "email": user['email']}
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 9. User Dashboard Data: Get submissions by user
@app.route('/api/user/my-items', methods=['GET'])
def get_user_items():
    try:
        owner_name = request.args.get('owner', '').strip()
        if not owner_name:
            return jsonify({"success": False, "error": "Owner name is required"}), 400

        items = list(ewaste_collection.find({"ownerName": {"$regex": f"^{owner_name}$", "$options": "i"}}))
        for doc in items:
            doc['_id'] = str(doc['_id'])
        return jsonify({"success": True, "items": items}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    # use_reloader=False prevents WinError 10038 socket crashes on Windows with Python 3.13
    app.run(port=5000, debug=True, use_reloader=False)