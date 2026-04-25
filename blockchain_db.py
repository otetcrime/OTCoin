"""
blockchain_db.py — OTCoin Blockchain dengan SQLite
Lebih cepat, lebih efisien dari JSON!
"""

import hashlib
import json
import time
import os
import sqlite3
import secrets
from typing import List, Optional

TOTAL_SUPPLY        = 51_000_000.0
MINING_REWARD       = 50.0
HALVING_INTERVAL    = 210_000
DIFFICULTY_START    = 4
DIFFICULTY_INTERVAL = 2016
TARGET_BLOCK_TIME   = 10
DB_FILE             = "otcoin.db"
NETWORK_ID          = "otcoin-mainnet-v2"
MIN_TX_FEE          = 0.001
MAX_MEMPOOL_SIZE    = 1000


class Transaction:
    def __init__(self, sender, recipient, amount,
                 signature="COINBASE", timestamp=None,
                 fee=0.0, network_id=NETWORK_ID, nonce=None):
        self.sender     = sender
        self.recipient  = recipient
        self.amount     = amount
        self.signature  = signature
        self.timestamp  = timestamp or time.time()
        self.fee        = fee
        self.network_id = network_id
        self.nonce      = nonce or secrets.token_hex(8)
        self.tx_id      = self._calc_id()

    def _calc_id(self):
        data = f"{self.sender}{self.recipient}{self.amount}{self.timestamp}{self.nonce}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self):
        return {
            "sender": self.sender, "recipient": self.recipient,
            "amount": self.amount, "signature": self.signature,
            "timestamp": self.timestamp, "fee": self.fee,
            "network_id": self.network_id, "nonce": self.nonce,
            "tx_id": self.tx_id,
        }

    def to_string(self):
        return f"{self.sender}{self.recipient}{self.amount}{self.timestamp}{self.nonce}"

    @classmethod
    def from_dict(cls, d):
        tx = cls(
            d["sender"], d["recipient"], d["amount"],
            d.get("signature", "COINBASE"),
            d.get("timestamp", time.time()),
            d.get("fee", 0.0),
            d.get("network_id", NETWORK_ID),
            d.get("nonce", secrets.token_hex(8))
        )
        tx.tx_id = d.get("tx_id", tx.tx_id)
        return tx


class Block:
    def __init__(self, index, transactions, previous_hash,
                 difficulty=DIFFICULTY_START, timestamp=None, nonce=0):
        self.index         = index
        self.timestamp     = timestamp or time.time()
        self.transactions  = transactions
        self.previous_hash = previous_hash
        self.difficulty    = difficulty
        self.nonce         = nonce
        self.merkle_root   = self._calc_merkle()
        self.hash          = self.calculate_hash()

    def _calc_merkle(self):
        if not self.transactions:
            return hashlib.sha256(b"empty").hexdigest()
        hashes = [hashlib.sha256(
            json.dumps(tx.to_dict(), sort_keys=True).encode()
        ).hexdigest() for tx in self.transactions]
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256((hashes[i] + hashes[i+1]).encode()).hexdigest()
                for i in range(0, len(hashes), 2)
            ]
        return hashes[0]

    def calculate_hash(self):
        raw = f"{self.index}{self.timestamp}{self.merkle_root}{self.previous_hash}{self.nonce}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def mine(self):
        target = "0" * self.difficulty
        print(f"  ⛏  Mining blok #{self.index} (difficulty={self.difficulty})...")
        start = time.time()
        while self.hash[:self.difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
        elapsed = time.time() - start
        print(f"  ✅ Blok #{self.index} ditemukan! ({elapsed:.2f}s)\n")

    def to_dict(self):
        return {
            "index": self.index, "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "difficulty": self.difficulty, "nonce": self.nonce,
            "merkle_root": self.merkle_root, "hash": self.hash,
        }


class BlockchainDB:
    """Blockchain dengan SQLite — lebih cepat dari JSON!"""

    def __init__(self):
        self.mempool      = []
        self.total_mined  = 0.0
        self.spent_nonces = set()
        self._init_db()
        self._load_state()

    def _init_db(self):
        """Inisialisasi database SQLite."""
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()

        # Tabel blocks
        cur.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY,
                idx INTEGER UNIQUE,
                timestamp REAL,
                previous_hash TEXT,
                merkle_root TEXT,
                hash TEXT UNIQUE,
                difficulty INTEGER,
                nonce INTEGER
            )
        """)

        # Tabel transactions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                tx_id TEXT UNIQUE,
                block_idx INTEGER,
                sender TEXT,
                recipient TEXT,
                amount REAL,
                fee REAL,
                signature TEXT,
                timestamp REAL,
                nonce TEXT,
                network_id TEXT,
                FOREIGN KEY (block_idx) REFERENCES blocks(idx)
            )
        """)

        # Tabel metadata
        cur.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Index untuk query cepat
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_sender ON transactions(sender)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_recipient ON transactions(recipient)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_idx)")

        self.conn.commit()
        print(f"✅ Database SQLite initialized: {DB_FILE}")

    def _load_state(self):
        """Load state dari database."""
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM metadata WHERE key='total_mined'")
        row = cur.fetchone()
        if row:
            self.total_mined = float(row["value"])
            count = cur.execute("SELECT COUNT(*) as c FROM blocks").fetchone()["c"]
            print(f"📂 Database dimuat: {count} blok | Total mined: Ꞵ{self.total_mined:,.1f} OTC\n")
        else:
            self._create_genesis()

    def _save_block(self, block: Block):
        """Simpan blok ke database."""
        cur = self.conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO blocks
            (idx, timestamp, previous_hash, merkle_root, hash, difficulty, nonce)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (block.index, block.timestamp, block.previous_hash,
              block.merkle_root, block.hash, block.difficulty, block.nonce))

        for tx in block.transactions:
            cur.execute("""
                INSERT OR REPLACE INTO transactions
                (tx_id, block_idx, sender, recipient, amount, fee,
                 signature, timestamp, nonce, network_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tx.tx_id, block.index, tx.sender, tx.recipient,
                  tx.amount, tx.fee, tx.signature, tx.timestamp,
                  tx.nonce, tx.network_id))

        cur.execute("""
            INSERT OR REPLACE INTO metadata (key, value)
            VALUES ('total_mined', ?)
        """, (str(self.total_mined),))

        self.conn.commit()

    def _create_genesis(self):
        genesis_tx = Transaction("SYSTEM", "genesis", 0, "GENESIS_OTCOIN_2025")
        genesis = Block(0, [genesis_tx], "0" * 64, DIFFICULTY_START)
        genesis.mine()
        self._save_block(genesis)
        print(f"🌐 Genesis block created!")

    def _get_latest_block(self) -> Optional[dict]:
        cur = self.conn.cursor()
        return cur.execute(
            "SELECT * FROM blocks ORDER BY idx DESC LIMIT 1"
        ).fetchone()

    def get_balance(self, address: str) -> float:
        """Hitung saldo langsung dari database — SUPER CEPAT!"""
        cur = self.conn.cursor()

        received = cur.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE recipient=?",
            (address,)
        ).fetchone()["total"]

        sent = cur.execute(
            "SELECT COALESCE(SUM(amount + fee), 0) as total FROM transactions WHERE sender=?",
            (address,)
        ).fetchone()["total"]

        return round(received - sent, 8)

    def get_current_reward(self) -> float:
        cur = self.conn.cursor()
        count = cur.execute("SELECT COUNT(*) as c FROM blocks").fetchone()["c"]
        halvings = count // HALVING_INTERVAL
        return MINING_REWARD / (2 ** halvings)

    def remaining_supply(self) -> float:
        return max(0.0, TOTAL_SUPPLY - self.total_mined)

    def get_current_difficulty(self) -> int:
        cur = self.conn.cursor()
        count = cur.execute("SELECT COUNT(*) as c FROM blocks").fetchone()["c"]
        if count < DIFFICULTY_INTERVAL:
            return DIFFICULTY_START
        latest = self._get_latest_block()
        return latest["difficulty"] if latest else DIFFICULTY_START

    def add_transaction(self, tx: Transaction):
        if tx.nonce in self.spent_nonces:
            raise ValueError("❌ Replay attack terdeteksi!")
        if tx.sender == "SYSTEM":
            self.mempool.append(tx)
            return
        if len(self.mempool) >= MAX_MEMPOOL_SIZE:
            raise ValueError("❌ Mempool penuh!")
        if tx.amount <= 0:
            raise ValueError("❌ Amount harus positif!")
        if tx.fee < MIN_TX_FEE:
            raise ValueError(f"❌ Fee minimum: {MIN_TX_FEE} OTC")

        balance = self.get_balance(tx.sender)
        pending = sum(t.amount + t.fee for t in self.mempool if t.sender == tx.sender)
        if balance - pending < tx.amount + tx.fee:
            raise ValueError("❌ Saldo tidak cukup!")

        self.mempool.append(tx)
        self.spent_nonces.add(tx.nonce)

    def mine_pending_transactions(self, miner_address: str) -> Block:
        reward = self.get_current_reward()
        if self.total_mined >= TOTAL_SUPPLY:
            reward = 0.0

        total_fees = sum(tx.fee for tx in self.mempool if tx.sender != "SYSTEM")
        total_reward = reward + total_fees

        reward_tx = Transaction(
            "SYSTEM", miner_address, total_reward, "COINBASE",
            nonce=f"CB_{time.time()}_{secrets.token_hex(4)}"
        )

        latest = self._get_latest_block()
        prev_hash = latest["hash"] if latest else "0" * 64
        prev_idx  = latest["idx"] if latest else -1

        new_block = Block(
            index=prev_idx + 1,
            transactions=[reward_tx] + self.mempool[:],
            previous_hash=prev_hash,
            difficulty=self.get_current_difficulty()
        )
        new_block.mine()
        self.total_mined += reward
        self._save_block(new_block)
        self.mempool.clear()

        pct = (self.total_mined / TOTAL_SUPPLY) * 100
        print(f"💰 Reward: Ꞵ{total_reward} OTC → {miner_address[:12]}...")
        print(f"📊 Mined: {self.total_mined:,.0f} / {TOTAL_SUPPLY:,.0f} ({pct:.4f}%)\n")
        return new_block

    def is_chain_valid(self) -> bool:
        cur = self.conn.cursor()
        blocks = cur.execute("SELECT * FROM blocks ORDER BY idx").fetchall()
        for i in range(1, len(blocks)):
            if blocks[i]["previous_hash"] != blocks[i-1]["hash"]:
                return False
        return True

    def print_stats(self):
        cur = self.conn.cursor()
        count = cur.execute("SELECT COUNT(*) as c FROM blocks").fetchone()["c"]
        tx_count = cur.execute("SELECT COUNT(*) as c FROM transactions").fetchone()["c"]
        pct = (self.total_mined / TOTAL_SUPPLY) * 100
        print("=" * 55)
        print("📊 OTCoin Network Stats — SQLite Edition")
        print("=" * 55)
        print(f"  Database      : {DB_FILE}")
        print(f"  Total Blok    : {count:,}")
        print(f"  Total TX      : {tx_count:,}")
        print(f"  Total Mined   : Ꞵ{self.total_mined:,.2f} OTC ({pct:.4f}%)")
        print(f"  Sisa Supply   : Ꞵ{self.remaining_supply():,.2f} OTC")
        print(f"  Block Reward  : Ꞵ{self.get_current_reward()} OTC")
        print(f"  Difficulty    : {self.get_current_difficulty()}")
        print("=" * 55)


if __name__ == "__main__":
    print("🚀 OTCoin Blockchain — SQLite Edition\n")
    bc = BlockchainDB()
    miner = "1892c373ab5ea6e6fcc9feb8622d1d424e3e38432"

    print("⛏️  Mining 3 blok...\n")
    for i in range(3):
        bc.mine_pending_transactions(miner)

    print(f"💳 Saldo: Ꞵ{bc.get_balance(miner):,.2f} OTC")
    print(f"🔍 Chain valid? {bc.is_chain_valid()}")
    bc.print_stats()
