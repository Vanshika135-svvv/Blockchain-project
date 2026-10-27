import base64
import datetime
from io import BytesIO
import os
import secrets
import time
import traceback
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
import qrcode
from web3 import Web3
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import certifi
    CA_FILE = certifi.where()
except ImportError:
    CA_FILE = None

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ---------------- 1. AUTO-DISCOVERY MONGODB ATLAS CONNECTION ----------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
mongo_connected = False
ewaste_collection = None
users_collection = None

memory_ewaste = []
memory_users = []

try:
    mongo_kwargs = {
        "serverSelectionTimeoutMS": 10000,
        "connectTimeoutMS": 10000,
        "socketTimeoutMS": 10000,
    }

    if "mongodb+srv://" in MONGO_URI or "ssl=true" in MONGO_URI.lower():
        mongo_kwargs["tls"] = True
        if CA_FILE:
            mongo_kwargs["tlsCAFile"] = CA_FILE
        else:
            mongo_kwargs["tlsAllowInvalidCertificates"] = True

    print("[*] Connecting to MongoDB Atlas cluster...")
    client = MongoClient(MONGO_URI, **mongo_kwargs)
    client.admin.command('ping')

    # Detect all non-system databases
    all_dbs = [d for d in client.list_database_names() if d not in ['admin', 'local', 'config']]
    print(f"[*] Available databases in Atlas: {all_dbs}")

    target_db = None
    target_coll = None

    # Priority 1: Check ecochain.ewaste
    if "ecochain" in all_dbs:
        db_candidate = client["ecochain"]
        if "ewaste" in db_candidate.list_collection_names() and db_candidate["ewaste"].count_documents({}) > 0:
            target_db = db_candidate
            target_coll = db_candidate["ewaste"]

    # Priority 2: Scan other databases for non-empty collections containing ewaste data
    if target_coll is None:
        for db_name in all_dbs:
            cand_db = client[db_name]
            for coll_name in cand_db.list_collection_names():
                count = cand_db[coll_name].count_documents({})
                if count > 0:
                    sample = cand_db[coll_name].find_one()
                    if sample and ("ewasteId" in sample or "deviceType" in sample or "status" in sample):
                        target_db = cand_db
                        target_coll = cand_db[coll_name]
                        print(f"[✓] Auto-detected e-waste data in database '{db_name}', collection '{coll_name}' ({count} records).")
                        break
            if target_coll is not None:
                break

    # Priority 3: Fallback to ecochain database
    if target_db is None:
        target_db = client["ecochain"]
        target_coll = target_db["ewaste"]

    ewaste_collection = target_coll
    users_collection = target_db["users"] if "users" in target_db.list_collection_names() else target_db["users"]

    record_count = ewaste_collection.count_documents({})
    mongo_connected = True
    print(f"[✓] Active database: '{target_db.name}', Collection: '{ewaste_collection.name}' with {record_count} records.")

except Exception as mongo_err:
    print(f"[!] Warning: Could not connect to Atlas ({mongo_err}).")
    print("[!] Ensure: 1) IP 0.0.0.0/0 is whitelisted in Atlas Network Access. 2) Credentials in .env are correct.")
    mongo_connected = False

# ---------------- 2. BLOCKCHAIN SETUP ----------------
BLOCKCHAIN_RPC_URL = os.getenv("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:8545")
w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_RPC_URL))

if not w3.is_connected():
    print(f"[!] Warning: Blockchain RPC unreachable at {BLOCKCHAIN_RPC_URL}. Ensure 'npx hardhat node' is running.")
else:
    print(f"[✓] Connected to Blockchain node at {BLOCKCHAIN_RPC_URL}.")

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
if PRIVATE_KEY:
    account = w3.eth.account.from_key(PRIVATE_KEY)
    default_account = account.address
    w3.eth.default_account = default_account
else:
    default_account = w3.eth.accounts[0] if (w3.is_connected() and len(w3.eth.accounts) > 0) else "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    w3.eth.default_account = default_account

CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x5FbDB2315678afecb367f032d93F642f64180aa3")

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

contract = None
try:
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=contract_abi)
except Exception as ce:
    print(f"[!] Contract binding error: {ce}")


def send_transaction(func_call):
    """Executes on-chain transaction with explicit gas budget."""
    if not w3.is_connected() or not default_account or not contract:
        return f"0xsimulated{secrets.token_hex(28)}"

    try:
        if PRIVATE_KEY:
            nonce = w3.eth.get_transaction_count(default_account)
            tx = func_call.build_transaction({
                'from': default_account,
                'nonce': nonce,
                'gas': 3000000,
                'gasPrice': w3.eth.gas_price
            })
            signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        else:
            tx_hash = func_call.transact({
                'from': default_account,
                'gas': 3000000
            })

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt.transactionHash.hex()
    except Exception as tx_err:
        print("[!] Contract Execution Error:", tx_err)
        return f"0xfailed{secrets.token_hex(28)}"


# ---------------- 3. API ENDPOINTS ----------------

@app.route('/api/ewaste/all', methods=['GET'])
def get_all_ewaste():
    try:
        items = []
        if mongo_connected and ewaste_collection is not None:
            raw = list(ewaste_collection.find())
            for doc in raw:
                doc['_id'] = str(doc['_id'])
                items.append(doc)
        else:
            items = memory_ewaste

        return jsonify({"success": True, "items": items}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ewaste/search', methods=['GET'])
def search_ewaste():
    try:
        query = request.args.get('q', '').strip()
        status_filter = request.args.get('status', '').strip()

        matched = []
        if mongo_connected and ewaste_collection is not None:
            filter_dict = {}
            if query:
                filter_dict["$or"] = [
                    {"ewasteId": {"$regex": query, "$options": "i"}},
                    {"ownerName": {"$regex": query, "$options": "i"}},
                    {"deviceType": {"$regex": query, "$options": "i"}}
                ]
            if status_filter and status_filter != 'ALL':
                filter_dict["status"] = status_filter

            raw = list(ewaste_collection.find(filter_dict))
            for doc in raw:
                doc['_id'] = str(doc['_id'])
                matched.append(doc)
        else:
            q_lower = query.lower()
            for item in memory_ewaste:
                matches_q = (
                    not query or
                    q_lower in item.get('ewasteId', '').lower() or
                    q_lower in item.get('ownerName', '').lower() or
                    q_lower in item.get('deviceType', '').lower()
                )
                matches_status = (not status_filter or status_filter == 'ALL' or item.get('status') == status_filter)
                if matches_q and matches_status:
                    matched.append(item)

        return jsonify({"success": True, "items": matched}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ewaste/<ewaste_id>', methods=['GET'])
def get_ewaste_details(ewaste_id):
    try:
        item = None
        if mongo_connected and ewaste_collection is not None:
            item = ewaste_collection.find_one({"ewasteId": ewaste_id})
            if item:
                item['_id'] = str(item['_id'])

        if not item:
            for it in memory_ewaste:
                if it.get("ewasteId") == ewaste_id:
                    item = it
                    break

        if not item:
            return jsonify({"success": False, "message": "E-Waste ID not found"}), 404

        return jsonify({"success": True, "item": item}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ewaste/register', methods=['POST'])
def register_ewaste():
    try:
        data = request.json or {}
        ewaste_id = f"EW-{int(time.time())}"
        device_type = data.get('deviceType', 'Electronic Device')
        weight_kg = float(data.get('weight', 1.0))
        weight_grams = int(weight_kg * 1000)

        blockchain_hash = send_transaction(
            contract.functions.registerEWaste(ewaste_id, device_type, weight_grams)
        )

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
                "handler": str(default_account),
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }]
        }

        if mongo_connected and ewaste_collection is not None:
            ewaste_collection.insert_one(new_item)
            new_item['_id'] = str(new_item['_id'])
        else:
            new_item['_id'] = secrets.token_hex(12)
            memory_ewaste.append(new_item)

        return jsonify({"success": True, "item": new_item, "txHash": blockchain_hash}), 201
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ewaste/update', methods=['POST'])
def update_ewaste():
    try:
        data = request.json or {}
        ewaste_id = data.get('ewasteId')
        new_status = data.get('status')

        if not ewaste_id or not new_status:
            return jsonify({"success": False, "error": "ewasteId and status are required."}), 400

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

        new_tx_entry = {
            "status": new_status,
            "hash": blockchain_hash,
            "handler": str(default_account),
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if mongo_connected and ewaste_collection is not None:
            ewaste_collection.update_one(
                {"ewasteId": ewaste_id},
                {
                    "$set": {"status": new_status},
                    "$push": {"transactionHashes": new_tx_entry}
                }
            )

        for item in memory_ewaste:
            if item.get("ewasteId") == ewaste_id:
                item["status"] = new_status
                item.setdefault("transactionHashes", []).append(new_tx_entry)
                break

        return jsonify({"success": True, "status": new_status, "txHash": blockchain_hash}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ewaste/recycle-breakdown', methods=['POST'])
def log_recycling_breakdown():
    try:
        data = request.json or {}
        ewaste_id = data.get('ewasteId')
        recovered_materials = data.get('materials', {})

        if not ewaste_id:
            return jsonify({"success": False, "error": "ewasteId is required"}), 400

        blockchain_hash = send_transaction(contract.functions.completeRecycling(ewaste_id))

        new_tx_entry = {
            "status": "RECYCLED",
            "hash": blockchain_hash,
            "handler": str(default_account),
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if mongo_connected and ewaste_collection is not None:
            ewaste_collection.update_one(
                {"ewasteId": ewaste_id},
                {
                    "$set": {
                        "status": "RECYCLED",
                        "recoveredMaterials": recovered_materials
                    },
                    "$push": {"transactionHashes": new_tx_entry}
                }
            )

        for item in memory_ewaste:
            if item.get("ewasteId") == ewaste_id:
                item["status"] = "RECYCLED"
                item["recoveredMaterials"] = recovered_materials
                item.setdefault("transactionHashes", []).append(new_tx_entry)
                break

        return jsonify({"success": True, "txHash": blockchain_hash, "materials": recovered_materials}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    try:
        data = request.json or {}
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not name or not email or not password:
            return jsonify({"success": False, "error": "All fields are required"}), 400

        user_doc = {
            "name": name,
            "email": email,
            "passwordHash": generate_password_hash(password),
            "createdAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if mongo_connected and users_collection is not None:
            if users_collection.find_one({"email": email}):
                return jsonify({"success": False, "error": "An account with this email already exists"}), 400
            users_collection.insert_one(user_doc)
        else:
            if any(u.get('email') == email for u in memory_users):
                return jsonify({"success": False, "error": "An account with this email already exists"}), 400
            memory_users.append(user_doc)

        token = secrets.token_hex(24)
        return jsonify({
            "success": True,
            "token": token,
            "user": {"name": name, "email": email}
        }), 201
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    try:
        data = request.json or {}
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        user = None
        if mongo_connected and users_collection is not None:
            user = users_collection.find_one({"email": email})

        if not user:
            for u in memory_users:
                if u.get('email') == email:
                    user = u
                    break

        if not user or not check_password_hash(user['passwordHash'], password):
            return jsonify({"success": False, "error": "Invalid email or password"}), 401

        token = secrets.token_hex(24)
        return jsonify({
            "success": True,
            "token": token,
            "user": {"name": user['name'], "email": user['email']}
        }), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/user/my-items', methods=['GET'])
def get_user_items():
    try:
        owner_name = request.args.get('owner', '').strip().lower()
        if not owner_name:
            return jsonify({"success": False, "error": "Owner name is required"}), 400

        matched = []
        if mongo_connected and ewaste_collection is not None:
            raw = list(ewaste_collection.find({"ownerName": {"$regex": f"^{owner_name}$", "$options": "i"}}))
            for doc in raw:
                doc['_id'] = str(doc['_id'])
                matched.append(doc)
        else:
            for item in memory_ewaste:
                if item.get("ownerName", "").lower() == owner_name:
                    matched.append(item)

        return jsonify({"success": True, "items": matched}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------- 4. SERVER RUNNER ----------------
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)