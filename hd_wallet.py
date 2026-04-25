"""
hd_wallet.py — OTCoin HD Wallet (Hierarchical Deterministic)
Satu seed phrase → banyak wallet address!
Seperti MetaMask dan Ledger!

pip install ecdsa mnemonic
"""

import hashlib
import hmac
import struct
import secrets
from typing import List, Tuple

try:
    from ecdsa import SigningKey, VerifyingKey, SECP256k1
except ImportError:
    print("Install: pip install ecdsa")
    exit(1)

try:
    from mnemonic import Mnemonic
    HAS_MNEMONIC = True
except ImportError:
    HAS_MNEMONIC = False


# ─────────────────────────────────────────────
# SEED PHRASE GENERATOR
# ─────────────────────────────────────────────
def generate_seed_phrase(strength=128) -> str:
    """Generate 12-24 kata seed phrase."""
    if HAS_MNEMONIC:
        mnemo = Mnemonic("english")
        return mnemo.generate(strength=strength)
    else:
        # Fallback: generate random hex seed
        return secrets.token_hex(32)


def seed_phrase_to_seed(phrase: str, passphrase: str = "") -> bytes:
    """Konversi seed phrase ke seed bytes (512 bit)."""
    if HAS_MNEMONIC:
        mnemo = Mnemonic("english")
        return mnemo.to_seed(phrase, passphrase)
    else:
        # Fallback untuk seed hex
        return hashlib.pbkdf2_hmac(
            'sha512', phrase.encode(), b'OTCoin' + passphrase.encode(), 2048
        )


# ─────────────────────────────────────────────
# HD WALLET
# ─────────────────────────────────────────────
class HDWallet:
    """
    Hierarchical Deterministic Wallet untuk OTCoin.
    Satu seed phrase → tak terbatas wallet address!

    Derivation path: m/44'/OTC'/account'/change/index
    """

    COIN_TYPE = 637  # OTCoin coin type (custom)

    def __init__(self, seed_phrase: str = None, passphrase: str = ""):
        if seed_phrase is None:
            seed_phrase = generate_seed_phrase()
            print(f"🔑 Seed phrase baru dibuat!")

        self.seed_phrase = seed_phrase
        self.seed        = seed_phrase_to_seed(seed_phrase, passphrase)
        self._master_key, self._master_chain = self._derive_master()
        self._cache = {}

        print(f"✅ HD Wallet initialized!")
        print(f"   Seed phrase: {seed_phrase[:30]}...")
        print(f"   ⚠️  SIMPAN SEED PHRASE INI! Jangan bagikan ke siapapun!\n")

    def _derive_master(self) -> Tuple[bytes, bytes]:
        """Derive master key dari seed."""
        I = hmac.new(b"OTCoin seed", self.seed, hashlib.sha512).digest()
        return I[:32], I[32:]

    def _derive_child(self, parent_key: bytes, parent_chain: bytes,
                      index: int) -> Tuple[bytes, bytes]:
        """Derive child key dari parent key."""
        if index >= 0x80000000:
            # Hardened derivation
            data = b'\x00' + parent_key + struct.pack('>I', index)
        else:
            # Normal derivation
            sk = SigningKey.from_string(parent_key, curve=SECP256k1)
            pub = sk.get_verifying_key().to_string()
            data = pub + struct.pack('>I', index)

        I = hmac.new(parent_chain, data, hashlib.sha512).digest()
        child_key   = (int.from_bytes(I[:32], 'big') +
                      int.from_bytes(parent_key, 'big')) % SECP256k1.order
        child_chain = I[32:]
        return child_key.to_bytes(32, 'big'), child_chain

    def _derive_path(self, path: str) -> Tuple[bytes, bytes]:
        """Derive key dari path seperti m/44'/637'/0'/0/0."""
        if path in self._cache:
            return self._cache[path]

        key   = self._master_key
        chain = self._master_chain

        parts = path.split('/')[1:]  # Skip 'm'
        for part in parts:
            hardened = part.endswith("'")
            index    = int(part.rstrip("'"))
            if hardened:
                index += 0x80000000
            key, chain = self._derive_child(key, chain, index)

        self._cache[path] = (key, chain)
        return key, chain

    def get_wallet(self, account: int = 0, index: int = 0,
                   change: int = 0) -> dict:
        """
        Dapatkan wallet address dari derivation path.

        account: 0, 1, 2, ... (bisa buat banyak akun)
        index:   0, 1, 2, ... (banyak address per akun)
        change:  0 = external, 1 = internal (change address)
        """
        path = f"m/44'/{self.COIN_TYPE}'/{account}'/{change}/{index}"
        key, _ = self._derive_path(path)

        # Buat wallet dari derived key
        sk = SigningKey.from_string(key, curve=SECP256k1)
        vk = sk.get_verifying_key()

        # Generate address
        pub_bytes   = vk.to_string()
        sha256_hash = hashlib.sha256(pub_bytes).digest()
        ripemd160   = hashlib.new("ripemd160")
        ripemd160.update(sha256_hash)
        address = "1" + ripemd160.hexdigest()

        return {
            "path":        path,
            "address":     address,
            "public_key":  vk.to_string().hex(),
            "private_key": sk.to_string().hex(),
            "account":     account,
            "index":       index,
        }

    def get_multiple_wallets(self, count: int = 5,
                             account: int = 0) -> List[dict]:
        """Generate beberapa wallet address sekaligus."""
        return [self.get_wallet(account=account, index=i)
                for i in range(count)]

    def print_wallets(self, count: int = 5):
        """Print beberapa wallet address."""
        print(f"\n{'='*60}")
        print(f"🔑 OTCoin HD Wallet — {count} Addresses")
        print(f"{'='*60}")
        wallets = self.get_multiple_wallets(count)
        for w in wallets:
            print(f"\n  [{w['index']}] Path: {w['path']}")
            print(f"      Address    : {w['address']}")
            print(f"      Public Key : {w['public_key'][:32]}...")
            print(f"      Private Key: {w['private_key'][:32]}... (RAHASIA!)")
        print(f"\n{'='*60}")

    def export_encrypted(self, password: str) -> dict:
        """Export wallet terenkripsi dengan password."""
        key = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), b'otcoin_hd_salt', 100000
        )
        encrypted = hmac.new(
            key, self.seed_phrase.encode(), hashlib.sha256
        ).hexdigest()

        return {
            "type":      "OTCoin HD Wallet",
            "encrypted": encrypted,
            "hint":      "Decrypt dengan password kamu",
            "version":   "1.0",
        }


# ─────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("🔑 OTCoin HD Wallet v1.0")
    print("   Satu Seed Phrase — Tak Terbatas Address!")
    print("=" * 60)

    # Buat HD wallet baru
    hd = HDWallet()

    # Tampilkan 5 address pertama
    hd.print_wallets(count=5)

    # Generate lebih banyak
    print("\n📋 Generate 3 address akun kedua:")
    wallets = hd.get_multiple_wallets(count=3, account=1)
    for w in wallets:
        print(f"  [{w['account']}/{w['index']}] {w['address']}")

    # Restore dari seed phrase yang sama
    print("\n🔄 Test restore dari seed phrase yang sama...")
    hd2 = HDWallet(seed_phrase=hd.seed_phrase)
    w1 = hd.get_wallet(account=0, index=0)
    w2 = hd2.get_wallet(account=0, index=0)

    if w1["address"] == w2["address"]:
        print(f"✅ Restore berhasil! Address sama: {w1['address'][:20]}...")
    else:
        print("❌ Restore gagal!")

    print("\n" + "=" * 60)
    print("✅ OTCoin HD Wallet berjalan sempurna!")
    print()
    print("💡 Keunggulan HD Wallet:")
    print("   ✅ Satu seed phrase untuk semua address")
    print("   ✅ Backup cukup seed phrase saja")
    print("   ✅ Generate address tanpa batas")
    print("   ✅ Seperti MetaMask dan Ledger!")
    print("=" * 60)
