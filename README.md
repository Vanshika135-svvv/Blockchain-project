# ♻ EcoChain: Blockchain-Based E-Waste Tracking & Verification

An end-to-end decentralized e-waste lifecycle verification protocol that records custody transitions onto an immutable, verifiable ledger[cite: 4, 8].

---

## 📌 Features

- **Decentralized State Transitions:** Smart contract enforcement ensuring irreversible custody updates (`REGISTERED` → `COLLECTED` → `IN TRANSIT` → `RECEIVED` → `RECYCLED`)[cite: 7, 8].
- **Cryptographic QR Badges:** Dynamic Base64-encoded QR codes linking physical device tags to public on-chain audit histories[cite: 4, 8].
- **ESG Carbon Offset Calculation:** Real-time formulaic calculation of avoided emissions computed at intake.
- **Secondary Material Logging:** Recycler-level yield reporting for reclaimed precious metals, copper, and thermoplastics.
- **Stakeholder Portals:** Dedicated interfaces for Consumers, Collection Hubs, Recyclers, and Public Auditing[cite: 8, 10].
- **Bento Grid Interface:** High-scannability Web3 dashboard layout.

---

## 🏗 Architecture & Tech Stack

- **Blockchain Layer:** Ethereum Localhost Node (Hardhat v2.22.0, Chain ID: 31337)
- **Smart Contract:** Solidity `0.8.28` (`EWasteTracker.sol` deployed at `0x5FbDB2315678afecb367f032d93F642f64180aa3`)
- **Backend API:** Python 3.13, Flask, Web3.py, PyMongo, python-dotenv
- **Database:** MongoDB Atlas (Cloud Cluster `ecochain`)
- **Frontend Client:** HTML5, CSS3 (Bento Grid System), JavaScript

---

## 🚀 Quickstart & Setup

### 1. Environment Variables (`.env`)
Create a `.env` file in the project root:
```env
MONGO_URI=mongodb+srv://<db_user>:<db_password>@<cluster>.mongodb.net/ecochain?retryWrites=true&w=majority
CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3
```
### 2. Launch Local Blockchain Node
```bash
# Terminal 1: Run local Ethereum validator node
npx hardhat node
```
### 3. Deploy Smart Contract
```bash
# Terminal 2: Deploy EWasteTracker to local network
npx hardhat run scripts/deploy.js --network localhost
```
### 4. Run Flask Backend Server
```bash
# Terminal 2 (after contract deployment)
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Backend API service runs on http://127.0.0.1:5000.
### 5. Launch Frontend Client Server
```bash
# Terminal 3: Serve client static directory
cd frontend
python -m http.server 5500
Open http://127.0.0.1:5500/index.html in your web browser.
```
##🔄 End-to-End Workflow Execution
User Registration (user.html): Log device parameters (e.g., Laptop, 2.4 kg) to invoke registerEWaste(), mine the genesis block receipt, and obtain the cryptographic QR verification badge.
Collection Center (collection.html): Query the asset ID to verify hardware specs, assume custody (COLLECTED), and seal the courier batch (IN TRANSIT).
Recycler Facility (recycler.html): Acknowledge dock arrival (RECEIVED), input post-shredding raw material mass (Copper, Plastic, Precious metals), and invoke completeRecycling() to finalize state as RECYCLED.
Lifecycle Audit Timeline (track.html?id=EW-...): Publicly verify the completed 5-stage progress indicator alongside raw mined Ethereum block transaction hashes.
Ledger Explorer (admin.html): Monitor protocol-wide inventory metrics, recovered mass, and filter live assets by custody status.
##🎓 Academic Attribution
Institution: Shri Vaishnav Vidyapeeth Vishwavidyalaya, Indore
Institute: Shri Vaishnav Institute of Information Technology
Department: Computer Science & Engineering / Artificial Intelligence & Data Science
Faculty Guide: Mr. Rohit Choubey
Project Team:
- Vanshika Tiwari (23100BTCSAII14332)
- Harman Kaur (23100BTCSAII14286)
- Dhanshri Patil (23100BTCSAII14282)
- Vaidika Laddha (23100BTCSAII14329)