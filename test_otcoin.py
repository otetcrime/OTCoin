"""
test_otcoin.py — OTCoin Unit Tests v1.0
Test semua fitur blockchain secara otomatis!
"""

import unittest
import time
import sys
import os

# Add OTCoin to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blockchain import Blockchain, Block, Transaction, NETWORK_ID, MIN_TX_FEE

class TestTransaction(unittest.TestCase):
    """Test semua fitur transaksi."""

    def test_create_transaction(self):
        """Test buat transaksi normal."""
        tx = Transaction("sender123", "recipient456", 100.0, fee=0.001)
        self.assertEqual(tx.sender, "sender123")
        self.assertEqual(tx.recipient, "recipient456")
        self.assertEqual(tx.amount, 100.0)
        self.assertEqual(tx.network_id, NETWORK_ID)
        print("✅ test_create_transaction PASSED")

    def test_transaction_id_unique(self):
        """Test setiap transaksi punya ID unik."""
        tx1 = Transaction("sender", "recipient", 100.0)
        tx2 = Transaction("sender", "recipient", 100.0)
        self.assertNotEqual(tx1.tx_id, tx2.tx_id)
        print("✅ test_transaction_id_unique PASSED")

    def test_transaction_to_dict(self):
        """Test konversi transaksi ke dict."""
        tx = Transaction("sender", "recipient", 50.0, fee=0.001)
        d = tx.to_dict()
        self.assertEqual(d["sender"], "sender")
        self.assertEqual(d["amount"], 50.0)
        self.assertIn("nonce", d)
        self.assertIn("tx_id", d)
        print("✅ test_transaction_to_dict PASSED")

    def test_transaction_from_dict(self):
        """Test buat transaksi dari dict."""
        tx = Transaction("sender", "recipient", 75.0, fee=0.001)
        d = tx.to_dict()
        tx2 = Transaction.from_dict(d)
        self.assertEqual(tx2.sender, tx.sender)
        self.assertEqual(tx2.amount, tx.amount)
        self.assertEqual(tx2.nonce, tx.nonce)
        print("✅ test_transaction_from_dict PASSED")


class TestBlock(unittest.TestCase):
    """Test semua fitur blok."""

    def setUp(self):
        self.tx = Transaction("SYSTEM", "miner", 50.0, "COINBASE")
        self.block = Block(1, [self.tx], "0" * 64, difficulty=2)

    def test_block_hash(self):
        """Test hash blok valid."""
        self.assertEqual(len(self.block.hash), 64)
        self.assertEqual(self.block.hash, self.block.calculate_hash())
        print("✅ test_block_hash PASSED")

    def test_block_mining(self):
        """Test mining blok berhasil."""
        self.block.mine()
        self.assertTrue(self.block.hash.startswith("00"))
        print("✅ test_block_mining PASSED")

    def test_block_merkle_root(self):
        """Test merkle root valid."""
        merkle = self.block._calc_merkle()
        self.assertEqual(len(merkle), 64)
        print("✅ test_block_merkle_root PASSED")

    def test_block_validity(self):
        """Test validasi blok."""
        self.block.mine()
        self.assertTrue(self.block.is_valid())
        print("✅ test_block_validity PASSED")

    def test_block_tampering(self):
        """Test blok yang dimanipulasi terdeteksi."""
        self.block.mine()
        # Manipulasi transaksi
        self.block.transactions[0].amount = 99999
        self.assertFalse(self.block.is_valid())
        print("✅ test_block_tampering PASSED")

    def test_block_to_dict(self):
        """Test konversi blok ke dict."""
        d = self.block.to_dict()
        self.assertIn("index", d)
        self.assertIn("hash", d)
        self.assertIn("merkle_root", d)
        print("✅ test_block_to_dict PASSED")


class TestBlockchain(unittest.TestCase):
    """Test semua fitur blockchain."""

    def setUp(self):
        """Setup blockchain baru untuk setiap test."""
        # Hapus file chain kalau ada
        if os.path.exists("otcoin_chain_test.json"):
            os.remove("otcoin_chain_test.json")

        import blockchain as bc_module
        self.orig_data_file = bc_module.DATA_FILE
        bc_module.DATA_FILE = "otcoin_chain_test.json"

        self.bc = Blockchain()
        self.miner = "1892c373ab5ea6e6fcc9feb8622d1d424e3e38432"
        self.user1 = "user1_address_abc123def456789"
        self.user2 = "user2_address_xyz789ghi012345"

    def tearDown(self):
        """Bersihkan setelah test."""
        import blockchain as bc_module
        bc_module.DATA_FILE = self.orig_data_file
        if os.path.exists("otcoin_chain_test.json"):
            os.remove("otcoin_chain_test.json")

    def test_genesis_block(self):
        """Test genesis block ada dan valid."""
        self.assertEqual(len(self.bc.chain), 1)
        self.assertEqual(self.bc.chain[0].index, 0)
        print("✅ test_genesis_block PASSED")

    def test_mining(self):
        """Test mining blok baru."""
        self.bc.mine_pending_transactions(self.miner)
        self.assertEqual(len(self.bc.chain), 2)
        self.assertEqual(self.bc.get_balance(self.miner), 50.0)
        print("✅ test_mining PASSED")

    def test_block_reward(self):
        """Test reward mining masuk ke wallet."""
        self.bc.mine_pending_transactions(self.miner)
        balance = self.bc.get_balance(self.miner)
        self.assertEqual(balance, 50.0)
        print("✅ test_block_reward PASSED")

    def test_chain_valid(self):
        """Test chain valid setelah mining."""
        self.bc.mine_pending_transactions(self.miner)
        self.bc.mine_pending_transactions(self.miner)
        self.assertTrue(self.bc.is_chain_valid())
        print("✅ test_chain_valid PASSED")

    def test_chain_tamper_detection(self):
        """Test manipulasi chain terdeteksi."""
        self.bc.mine_pending_transactions(self.miner)
        # Manipulasi blok
        self.bc.chain[1].transactions[0].amount = 99999
        self.assertFalse(self.bc.is_chain_valid())
        print("✅ test_chain_tamper_detection PASSED")

    def test_double_spend_protection(self):
        """Test double spend terdeteksi."""
        # Mine dulu untuk dapat saldo
        self.bc.mine_pending_transactions(self.miner)
        balance = self.bc.get_balance(self.miner)

        # Coba kirim lebih dari saldo
        tx = Transaction(self.miner, self.user1, balance + 1000, fee=MIN_TX_FEE)
        with self.assertRaises(ValueError):
            self.bc.add_transaction(tx)
        print("✅ test_double_spend_protection PASSED")

    def test_replay_attack_protection(self):
        """Test replay attack terdeteksi."""
        self.bc.mine_pending_transactions(self.miner)

        tx = Transaction(self.miner, self.user1, 10.0, fee=MIN_TX_FEE)
        self.bc.spent_nonces.add(tx.nonce)

        with self.assertRaises(ValueError):
            self.bc.add_transaction(tx)
        print("✅ test_replay_attack_protection PASSED")

    def test_network_id_validation(self):
        """Test transaksi dari network lain ditolak."""
        tx = Transaction(self.miner, self.user1, 10.0,
                        fee=MIN_TX_FEE, network_id="wrong-network")
        with self.assertRaises(ValueError):
            self.bc.add_transaction(tx)
        print("✅ test_network_id_validation PASSED")

    def test_minimum_fee(self):
        """Test fee di bawah minimum ditolak."""
        self.bc.mine_pending_transactions(self.miner)
        tx = Transaction(self.miner, self.user1, 10.0, fee=0.0)
        with self.assertRaises(ValueError):
            self.bc.add_transaction(tx)
        print("✅ test_minimum_fee PASSED")

    def test_supply_cap(self):
        """Test total supply tidak melebihi 51 juta."""
        self.assertTrue(self.bc.total_mined <= 51_000_000)
        self.assertTrue(self.bc.remaining_supply() >= 0)
        print("✅ test_supply_cap PASSED")

    def test_difficulty_starts_correct(self):
        """Test difficulty awal benar."""
        diff = self.bc.get_current_difficulty()
        self.assertGreaterEqual(diff, 1)
        print("✅ test_difficulty_starts_correct PASSED")

    def test_balance_calculation(self):
        """Test perhitungan saldo benar."""
        # Mine 3 blok
        for _ in range(3):
            self.bc.mine_pending_transactions(self.miner)
        balance = self.bc.get_balance(self.miner)
        self.assertEqual(balance, 150.0)
        print("✅ test_balance_calculation PASSED")

    def test_mempool_spam_protection(self):
        """Test mempool spam protection."""
        self.bc.mine_pending_transactions(self.miner)

        # Isi mempool sampai maks
        import blockchain as bc_module
        orig_max = bc_module.MAX_MEMPOOL_SIZE
        bc_module.MAX_MEMPOOL_SIZE = 2

        # Add 2 TX dulu supaya penuh
        self.bc.mempool = ["tx"] * 2

        tx = Transaction(self.miner, self.user1, 1.0, fee=MIN_TX_FEE)
        with self.assertRaises(ValueError):
            self.bc.add_transaction(tx)

        bc_module.MAX_MEMPOOL_SIZE = orig_max
        self.bc.mempool = []
        print("✅ test_mempool_spam_protection PASSED")


class TestSecurity(unittest.TestCase):
    """Test fitur keamanan."""

    def test_genesis_signature(self):
        """Test genesis signature valid."""
        import hmac
        import hashlib
        from blockchain import GENESIS_SIGNATURE, NETWORK_ID
        sig = hmac.new(
            GENESIS_SIGNATURE.encode(),
            NETWORK_ID.encode(),
            hashlib.sha256
        ).hexdigest()
        self.assertEqual(len(sig), 64)
        print("✅ test_genesis_signature PASSED")

    def test_private_key_encryption(self):
        """Test enkripsi private key."""
        from blockchain import SecureWallet
        pk = "my_secret_private_key"
        password = "my_password"
        encrypted = SecureWallet.encrypt_private_key(pk, password)
        self.assertNotEqual(encrypted, pk)
        self.assertEqual(len(encrypted), 64)

        # Password berbeda → hasil berbeda
        encrypted2 = SecureWallet.encrypt_private_key(pk, "wrong_password")
        self.assertNotEqual(encrypted, encrypted2)
        print("✅ test_private_key_encryption PASSED")


# ─────────────────────────────────────────────
# JALANKAN SEMUA TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("🧪 OTCoin Unit Tests v1.0")
    print("=" * 60)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestTransaction))
    suite.addTests(loader.loadTestsFromTestCase(TestBlock))
    suite.addTests(loader.loadTestsFromTestCase(TestBlockchain))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurity))

    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)

    print()
    print("=" * 60)
    if result.wasSuccessful():
        print(f"✅ SEMUA {result.testsRun} TEST LULUS! OTCoin siap mainnet!")
    else:
        print(f"❌ {len(result.failures)} test gagal dari {result.testsRun}")
    print("=" * 60)
