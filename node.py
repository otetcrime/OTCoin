"""
node.py — Node P2P dengan WebSocket untuk jaringan MyCoin
Jalankan: pip install websockets ecdsa

Cara pakai:
  Terminal 1 (node pertama / bootstrap):
    python node.py --port 6001

  Terminal 2 (node kedua, hubungkan ke node 1):
    python node.py --port 6002 --peers ws://localhost:6001

  Terminal 3 (node ketiga):
    python node.py --port 6003 --peers ws://localhost:6001,ws://localhost:6002
"""

import asyncio
import json
import argparse
import time
import hashlib
from typing import Set, List, Optional

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError:
    print("Install dulu: pip install websockets")
    exit(1)

from blockchain import Blockchain, Block, Transaction


# ─────────────────────────────────────────────
# TIPE PESAN P2P
# ─────────────────────────────────────────────
MSG_QUERY_LATEST       = "QUERY_LATEST_BLOCK"
MSG_QUERY_ALL          = "QUERY_ALL_CHAIN"
MSG_RESPONSE_CHAIN     = "RESPONSE_CHAIN"
MSG_RESPONSE_LATEST    = "RESPONSE_LATEST_BLOCK"
MSG_NEW_TRANSACTION    = "NEW_TRANSACTION"
MSG_QUERY_MEMPOOL      = "QUERY_MEMPOOL"
MSG_RESPONSE_MEMPOOL   = "RESPONSE_MEMPOOL"


def make_message(msg_type: str, data=None) -> str:
    return json.dumps({"type": msg_type, "data": data, "timestamp": time.time()})


# ─────────────────────────────────────────────
# SERIALISASI BLOK
# ─────────────────────────────────────────────
def block_to_dict(block: Block) -> dict:
    return {
        "index": block.index,
        "timestamp": block.timestamp,
        "transactions": [tx.to_dict() for tx in block.transactions],
        "previous_hash": block.previous_hash,
        "nonce": block.nonce,
        "hash": block.hash,
        "difficulty": block.difficulty,
    }

def dict_to_block(d: dict) -> Block:
    txs = [
        Transaction(
            sender=t["sender"],
            recipient=t["recipient"],
            amount=t["amount"],
            signature=t.get("signature", ""),
        )
        for t in d["transactions"]
    ]
    block = Block.__new__(Block)
    block.index = d["index"]
    block.timestamp = d["timestamp"]
    block.transactions = txs
    block.previous_hash = d["previous_hash"]
    block.nonce = d["nonce"]
    block.hash = d["hash"]
    block.difficulty = d["difficulty"]
    return block


# ─────────────────────────────────────────────
# NODE P2P
# ─────────────────────────────────────────────
class P2PNode:
    def __init__(self, port: int, peers: List[str] = None):
        self.port = port
        self.blockchain = Blockchain()
        self.peers: Set[WebSocketServerProtocol] = set()    # koneksi aktif
        self.peer_urls: List[str] = peers or []
        self.node_id = f"node-{port}"

    # ── SERVER ────────────────────────────────
    async def start_server(self):
        print(f"\n🌐 Node [{self.node_id}] mendengarkan di ws://localhost:{self.port}")
        async with websockets.serve(self._handle_connection, "localhost", self.port):
            await asyncio.Future()  # jalankan selamanya

    async def _handle_connection(self, websocket: WebSocketServerProtocol):
        self.peers.add(websocket)
        peer_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        print(f"  🔗 Peer terhubung: {peer_addr} (total: {len(self.peers)})")

        # Saat peer baru terhubung, minta chain terbaru
        await websocket.send(make_message(MSG_QUERY_LATEST))

        try:
            async for raw in websocket:
                await self._handle_message(websocket, raw)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.peers.discard(websocket)
            print(f"  ❌ Peer terputus: {peer_addr} (tersisa: {len(self.peers)})")

    # ── CONNECT KE PEER LAIN ──────────────────
    async def connect_to_peers(self):
        for url in self.peer_urls:
            try:
                print(f"  📡 Menghubungkan ke {url}...")
                websocket = await websockets.connect(url)
                self.peers.add(websocket)
                print(f"  ✅ Terhubung ke {url}")
                # Dengarkan pesan dari peer ini
                asyncio.create_task(self._listen_to_peer(websocket))
                # Minta chain terbaru
                await websocket.send(make_message(MSG_QUERY_LATEST))
            except Exception as e:
                print(f"  ⚠️  Gagal terhubung ke {url}: {e}")

    async def _listen_to_peer(self, websocket):
        try:
            async for raw in websocket:
                await self._handle_message(websocket, raw)
        except websockets.exceptions.ConnectionClosed:
            self.peers.discard(websocket)

    # ── PROSES PESAN ──────────────────────────
    async def _handle_message(self, websocket, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type")
        data = msg.get("data")

        if msg_type == MSG_QUERY_LATEST:
            # Peer minta blok terbaru
            latest = block_to_dict(self.blockchain.latest_block)
            await websocket.send(make_message(MSG_RESPONSE_LATEST, latest))

        elif msg_type == MSG_QUERY_ALL:
            # Peer minta seluruh chain
            chain = [block_to_dict(b) for b in self.blockchain.chain]
            await websocket.send(make_message(MSG_RESPONSE_CHAIN, chain))

        elif msg_type == MSG_RESPONSE_LATEST:
            # Terima blok terbaru dari peer
            received_block = dict_to_block(data)
            await self._handle_received_latest(websocket, received_block)

        elif msg_type == MSG_RESPONSE_CHAIN:
            # Terima seluruh chain dari peer
            received_chain = [dict_to_block(d) for d in data]
            await self._handle_received_chain(received_chain)

        elif msg_type == MSG_NEW_TRANSACTION:
            # Transaksi baru dari peer
            tx = Transaction(
                sender=data["sender"],
                recipient=data["recipient"],
                amount=data["amount"],
                signature=data.get("signature", ""),
            )
            if not any(
                t.sender == tx.sender and t.recipient == tx.recipient and t.amount == tx.amount
                for t in self.blockchain.mempool
            ):
                print(f"  📬 [{self.node_id}] Transaksi baru dari peer: {tx}")
                self.blockchain.mempool.append(tx)

        elif msg_type == MSG_QUERY_MEMPOOL:
            mempool_data = [tx.to_dict() for tx in self.blockchain.mempool]
            await websocket.send(make_message(MSG_RESPONSE_MEMPOOL, mempool_data))

    # ── SINKRONISASI CHAIN ────────────────────
    async def _handle_received_latest(self, websocket, received: Block):
        latest = self.blockchain.latest_block

        if received.index > latest.index:
            print(f"\n  ⚠️  [{self.node_id}] Peer punya chain lebih panjang (index {received.index} > {latest.index})")
            if received.previous_hash == latest.hash:
                # Blok langsung nyambung — tambahkan
                if self._is_valid_new_block(received, latest):
                    self.blockchain.chain.append(received)
                    print(f"  ✅ Blok #{received.index} ditambahkan dari peer")
                    await self.broadcast(make_message(MSG_RESPONSE_LATEST, block_to_dict(received)))
            else:
                # Tidak nyambung — minta seluruh chain
                print(f"  🔄 Meminta seluruh chain dari peer...")
                await websocket.send(make_message(MSG_QUERY_ALL))
        else:
            print(f"  ✅ [{self.node_id}] Chain sudah up-to-date (index {latest.index})")

    async def _handle_received_chain(self, received_chain: List[Block]):
        if len(received_chain) <= len(self.blockchain.chain):
            print(f"  ℹ️  [{self.node_id}] Chain yang diterima tidak lebih panjang. Abaikan.")
            return

        if self._is_valid_chain(received_chain):
            print(f"  🔄 [{self.node_id}] Mengganti chain dengan chain peer yang lebih panjang ({len(received_chain)} blok)")
            self.blockchain.chain = received_chain
            await self.broadcast(
                make_message(MSG_RESPONSE_LATEST, block_to_dict(received_chain[-1]))
            )
        else:
            print(f"  ❌ [{self.node_id}] Chain dari peer tidak valid!")

    def _is_valid_new_block(self, new_block: Block, prev_block: Block) -> bool:
        if new_block.previous_hash != prev_block.hash:
            return False
        if new_block.hash != new_block.calculate_hash():
            return False
        if new_block.hash[: new_block.difficulty] != "0" * new_block.difficulty:
            return False
        return True

    def _is_valid_chain(self, chain: List[Block]) -> bool:
        for i in range(1, len(chain)):
            if not self._is_valid_new_block(chain[i], chain[i - 1]):
                return False
        return True

    # ── BROADCAST ─────────────────────────────
    async def broadcast(self, message: str):
        """Kirim pesan ke semua peer yang terhubung."""
        if not self.peers:
            return
        disconnected = set()
        for peer in self.peers:
            try:
                await peer.send(message)
            except Exception:
                disconnected.add(peer)
        self.peers -= disconnected

    async def broadcast_transaction(self, tx: Transaction):
        """Broadcast transaksi baru ke semua peer."""
        print(f"\n  📢 [{self.node_id}] Broadcasting transaksi: {tx}")
        await self.broadcast(make_message(MSG_NEW_TRANSACTION, tx.to_dict()))

    # ── MINING ────────────────────────────────
    async def mine(self, miner_address: str):
        if not self.blockchain.mempool:
            print(f"\n  ℹ️  [{self.node_id}] Mempool kosong, tidak ada yang di-mine")
            return
        print(f"\n  ⛏  [{self.node_id}] Mulai mining...")
        new_block = self.blockchain.mine_pending_transactions(miner_address)
        # Broadcast blok baru ke semua peer
        await self.broadcast(
            make_message(MSG_RESPONSE_LATEST, block_to_dict(new_block))
        )
        print(f"  📢 [{self.node_id}] Blok #{new_block.index} dibroadcast ke {len(self.peers)} peer")

    # ── STATUS ────────────────────────────────
    def status(self):
        print(f"\n{'='*50}")
        print(f"  Node    : {self.node_id}")
        print(f"  Port    : {self.port}")
        print(f"  Peers   : {len(self.peers)}")
        print(f"  Blok    : {len(self.blockchain.chain)}")
        print(f"  Mempool : {len(self.blockchain.mempool)} transaksi")
        print(f"  Latest  : #{self.blockchain.latest_block.index} {self.blockchain.latest_block.hash[:16]}...")
        print(f"{'='*50}\n")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser(description="MyCoin P2P Node")
    parser.add_argument("--port", type=int, default=6001, help="Port WebSocket node ini")
    parser.add_argument("--peers", type=str, default="", help="URL peer (comma-separated), e.g. ws://localhost:6002")
    parser.add_argument("--miner", type=str, default="miner_default_address", help="Address wallet miner")
    args = parser.parse_args()

    peer_list = [p.strip() for p in args.peers.split(",") if p.strip()]

    node = P2PNode(port=args.port, peers=peer_list)
    node.status()

    # Jalankan server + koneksi ke peer secara bersamaan
    server_task = asyncio.create_task(node.start_server())

    # Beri sedikit delay lalu hubungkan ke peer
    await asyncio.sleep(0.5)
    if peer_list:
        await node.connect_to_peers()

    # Contoh: demo kirim transaksi dan mining setelah 3 detik
    async def demo_activity():
        await asyncio.sleep(3)
        print(f"\n{'─'*50}")
        print(f"  🎮 Demo: Menambah transaksi ke mempool node {args.port}...")
        tx = Transaction("demo_sender", args.miner, 10.0)
        node.blockchain.mempool.append(tx)
        await node.broadcast_transaction(tx)

        await asyncio.sleep(2)
        await node.mine(args.miner)
        node.status()

    asyncio.create_task(demo_activity())
    await server_task


if __name__ == "__main__":
    asyncio.run(main())
