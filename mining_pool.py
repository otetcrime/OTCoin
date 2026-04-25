"""
mining_pool.py — OTCoin Mining Pool v1.0
Banyak orang mining bersama — reward dibagi rata!

Cara pakai:
  Server: python mining_pool.py
  Miner : python miner.py --pool ws://76.13.192.203:7001
"""

import asyncio
import json
import time
import hashlib
import secrets
from typing import Dict, Set

try:
    import websockets
except ImportError:
    print("Install: pip install websockets")
    exit(1)

from blockchain import Blockchain, Transaction

# ─────────────────────────────────────────────
# KONFIGURASI POOL
# ─────────────────────────────────────────────
POOL_ADDRESS = "1892c373ab5ea6e6fcc9feb8622d1d424e3e38432"
POOL_FEE     = 0.01   # 1% fee untuk pool operator
POOL_PORT    = 7001
POOL_NAME    = "OTCoin Official Pool"


class MiningPool:
    def __init__(self):
        self.blockchain     = Blockchain()
        self.miners: Dict   = {}  # address → {shares, connected_at}
        self.connections: Set = set()
        self.total_shares   = 0
        self.blocks_found   = 0
        self.start_time     = time.time()

    async def handle_miner(self, websocket):
        """Handle koneksi miner baru."""
        miner_addr = None
        self.connections.add(websocket)

        try:
            async for message in websocket:
                data = json.loads(message)
                cmd  = data.get("cmd")

                if cmd == "join":
                    miner_addr = data.get("address")
                    if miner_addr not in self.miners:
                        self.miners[miner_addr] = {
                            "shares": 0,
                            "earned": 0.0,
                            "connected_at": time.time()
                        }
                    print(f"⛏️ Miner joined: {miner_addr[:16]}...")
                    await websocket.send(json.dumps({
                        "cmd": "welcome",
                        "pool": POOL_NAME,
                        "fee": f"{POOL_FEE*100}%",
                        "miners": len(self.miners),
                        "blocks": self.blocks_found
                    }))

                elif cmd == "share" and miner_addr:
                    # Miner submit share (bukti kerja)
                    nonce = data.get("nonce")
                    block_hash = data.get("hash")

                    if block_hash and block_hash.startswith("0" * self.blockchain.get_current_difficulty()):
                        self.miners[miner_addr]["shares"] += 1
                        self.total_shares += 1
                        print(f"✅ Valid share dari {miner_addr[:12]}... "
                              f"(total shares: {self.total_shares})")

                        await websocket.send(json.dumps({
                            "cmd": "share_accepted",
                            "shares": self.miners[miner_addr]["shares"]
                        }))

                elif cmd == "stats":
                    await websocket.send(json.dumps(self._get_stats()))

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connections.discard(websocket)
            if miner_addr:
                print(f"❌ Miner disconnected: {miner_addr[:16]}...")

    async def mine_loop(self):
        """Loop mining pool — mine blok dan distribusi reward."""
        print(f"⛏️ Pool mining loop started...")
        while True:
            try:
                if len(self.miners) > 0:
                    # Mine blok baru
                    new_block = self.blockchain.mine_pending_transactions(POOL_ADDRESS)
                    self.blocks_found += 1

                    # Distribusi reward
                    reward = self.blockchain.get_current_reward()
                    await self._distribute_reward(reward, new_block.index)

                    print(f"\n🎉 Block #{new_block.index} ditemukan!")
                    print(f"💰 Reward: {reward} OTC dibagi ke {len(self.miners)} miner")

                    # Broadcast ke semua miner
                    await self._broadcast({
                        "cmd": "block_found",
                        "block": new_block.index,
                        "reward": reward,
                        "miners": len(self.miners)
                    })

                    # Reset shares
                    for addr in self.miners:
                        self.miners[addr]["shares"] = 0
                    self.total_shares = 0

                await asyncio.sleep(1)

            except Exception as e:
                print(f"Pool error: {e}")
                await asyncio.sleep(5)

    async def _distribute_reward(self, total_reward, block_index):
        """Distribusi reward berdasarkan shares."""
        if self.total_shares == 0 or not self.miners:
            return

        # Potong fee pool
        pool_fee = total_reward * POOL_FEE
        distributable = total_reward - pool_fee

        print(f"\n💰 Distribusi Reward Block #{block_index}")
        print(f"   Total reward  : {total_reward} OTC")
        print(f"   Pool fee (1%) : {pool_fee:.4f} OTC")
        print(f"   Distributable : {distributable:.4f} OTC")

        for addr, info in self.miners.items():
            if info["shares"] > 0 and self.total_shares > 0:
                share_pct = info["shares"] / self.total_shares
                miner_reward = distributable * share_pct
                info["earned"] += miner_reward

                print(f"   {addr[:12]}... → {miner_reward:.4f} OTC "
                      f"({share_pct*100:.1f}%)")

                # Kirim notifikasi ke miner
                await self._broadcast({
                    "cmd": "reward",
                    "address": addr,
                    "amount": miner_reward,
                    "block": block_index
                })

    async def _broadcast(self, data):
        """Broadcast pesan ke semua miner."""
        if not self.connections:
            return
        msg = json.dumps(data)
        disconnected = set()
        for ws in self.connections:
            try:
                await ws.send(msg)
            except:
                disconnected.add(ws)
        self.connections -= disconnected

    def _get_stats(self):
        uptime = (time.time() - self.start_time) / 60
        return {
            "pool_name":    POOL_NAME,
            "pool_address": POOL_ADDRESS,
            "pool_fee":     f"{POOL_FEE*100}%",
            "miners":       len(self.miners),
            "blocks_found": self.blocks_found,
            "total_shares": self.total_shares,
            "uptime_min":   round(uptime, 1),
            "total_mined":  self.blockchain.total_mined,
        }

    async def start(self):
        print(f"=" * 55)
        print(f"🏊 {POOL_NAME}")
        print(f"=" * 55)
        print(f"  Pool Address : {POOL_ADDRESS[:20]}...")
        print(f"  Pool Fee     : {POOL_FEE*100}%")
        print(f"  Port         : {POOL_PORT}")
        print(f"  Connect via  : ws://76.13.192.203:{POOL_PORT}")
        print(f"=" * 55)

        # Jalankan server dan mining loop bersamaan
        server = websockets.serve(self.handle_miner, "0.0.0.0", POOL_PORT)
        async with server:
            print(f"✅ Pool server running on port {POOL_PORT}!")
            await self.mine_loop()


if __name__ == "__main__":
    pool = MiningPool()
    asyncio.run(pool.start())
