"""
OTCoin Miner — GUI Application
Tinggal klik Start Mining!
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import sys
import os

# ─────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────
APP_NAME    = "OTCoin Miner"
APP_VERSION = "v1.0"
NODE_URL    = "ws://76.13.192.203:6001"
WEBSITE     = "otcoin.org"

GOLD        = "#F4A717"
GOLD_DARK   = "#C97B00"
GOLD_LIGHT  = "#FFD166"
BG_DARK     = "#03030A"
BG_MID      = "#07080F"
BG_SURF     = "#0C0D17"
TEXT_COLOR  = "#E8E8F0"
DIM_COLOR   = "#5A5C78"
GREEN       = "#00C896"
RED         = "#FF5060"


class OTCoinMinerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"⛏️ {APP_NAME} {APP_VERSION}")
        self.root.geometry("600x700")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(False, False)

        self.mining = False
        self.blockchain = None
        self.total_blocks = 0
        self.total_earned = 0.0
        self.start_time = None
        self.mining_thread = None

        self._build_ui()

    def _build_ui(self):
        # ── HEADER ──────────────────────────────
        header = tk.Frame(self.root, bg=BG_MID, pady=16)
        header.pack(fill="x")

        tk.Label(header, text="🪙 OTCOIN", font=("Georgia", 28, "bold"),
                 bg=BG_MID, fg=GOLD_LIGHT).pack()
        tk.Label(header, text="One Transaction. All Chains.",
                 font=("Georgia", 11, "italic"),
                 bg=BG_MID, fg=DIM_COLOR).pack()
        tk.Label(header, text=f"Mining Software {APP_VERSION}",
                 font=("Courier", 9),
                 bg=BG_MID, fg=DIM_COLOR).pack()

        # ── WALLET INPUT ─────────────────────────
        wallet_frame = tk.Frame(self.root, bg=BG_DARK, pady=16, padx=24)
        wallet_frame.pack(fill="x")

        tk.Label(wallet_frame, text="YOUR WALLET ADDRESS",
                 font=("Courier", 9), bg=BG_DARK, fg=DIM_COLOR,
                 anchor="w").pack(fill="x")

        self.wallet_entry = tk.Entry(
            wallet_frame, font=("Courier", 11),
            bg=BG_SURF, fg=TEXT_COLOR,
            insertbackground=GOLD,
            relief="flat", bd=8
        )
        self.wallet_entry.pack(fill="x", pady=4)
        self.wallet_entry.insert(0, "Enter your OTCoin wallet address...")
        self.wallet_entry.bind("<FocusIn>", self._clear_placeholder)

        tk.Label(wallet_frame,
                 text="💡 Don't have a wallet? Download wallet.py from otcoin.org",
                 font=("Courier", 8), bg=BG_DARK, fg=DIM_COLOR).pack(anchor="w")

        # ── STATS ────────────────────────────────
        stats_frame = tk.Frame(self.root, bg=BG_DARK, padx=24)
        stats_frame.pack(fill="x")

        stats_grid = tk.Frame(stats_frame, bg=BG_DARK)
        stats_grid.pack(fill="x")

        # Stat cards
        self.stat_balance = self._stat_card(stats_grid, "0.00", "OTC EARNED", 0)
        self.stat_blocks  = self._stat_card(stats_grid, "0", "BLOCKS MINED", 1)
        self.stat_uptime  = self._stat_card(stats_grid, "0m", "UPTIME", 2)
        self.stat_status  = self._stat_card(stats_grid, "IDLE", "STATUS", 3)

        # ── PROGRESS ─────────────────────────────
        prog_frame = tk.Frame(self.root, bg=BG_DARK, padx=24, pady=8)
        prog_frame.pack(fill="x")

        tk.Label(prog_frame, text="SUPPLY MINED",
                 font=("Courier", 8), bg=BG_DARK, fg=DIM_COLOR).pack(anchor="w")

        self.progress = ttk.Progressbar(
            prog_frame, length=552, mode="determinate",
            maximum=51000000
        )
        self.progress.pack(fill="x", pady=4)

        self.progress_label = tk.Label(
            prog_frame, text="0 / 51,000,000 OTC",
            font=("Courier", 8), bg=BG_DARK, fg=DIM_COLOR
        )
        self.progress_label.pack(anchor="e")

        # ── START BUTTON ─────────────────────────
        btn_frame = tk.Frame(self.root, bg=BG_DARK, padx=24, pady=8)
        btn_frame.pack(fill="x")

        self.start_btn = tk.Button(
            btn_frame,
            text="⛏️  START MINING",
            font=("Georgia", 14, "bold"),
            bg=GOLD, fg="#000000",
            activebackground=GOLD_DARK,
            activeforeground="#000000",
            relief="flat", bd=0,
            pady=14, padx=24,
            cursor="hand2",
            command=self.toggle_mining
        )
        self.start_btn.pack(fill="x")

        # ── LOG ──────────────────────────────────
        log_frame = tk.Frame(self.root, bg=BG_DARK, padx=24, pady=8)
        log_frame.pack(fill="both", expand=True)

        tk.Label(log_frame, text="MINING LOG",
                 font=("Courier", 8), bg=BG_DARK, fg=DIM_COLOR).pack(anchor="w")

        self.log = scrolledtext.ScrolledText(
            log_frame,
            font=("Courier", 9),
            bg=BG_SURF, fg=TEXT_COLOR,
            relief="flat", bd=4,
            state="disabled",
            height=10
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("gold", foreground=GOLD)
        self.log.tag_config("green", foreground=GREEN)
        self.log.tag_config("red", foreground=RED)
        self.log.tag_config("dim", foreground=DIM_COLOR)

        # ── FOOTER ───────────────────────────────
        footer = tk.Frame(self.root, bg=BG_MID, pady=8)
        footer.pack(fill="x", side="bottom")

        tk.Label(footer,
                 text=f"🌍 {WEBSITE}  |  📡 Node: {NODE_URL}  |  © 2025 OTCoin Foundation",
                 font=("Courier", 8), bg=BG_MID, fg=DIM_COLOR).pack()

        self._log("Welcome to OTCoin Miner!", "gold")
        self._log(f"Node: {NODE_URL}", "dim")
        self._log("Enter your wallet address and click START MINING", "dim")

    def _stat_card(self, parent, value, label, col):
        frame = tk.Frame(parent, bg=BG_SURF, padx=12, pady=12,
                        relief="flat", bd=0)
        frame.grid(row=0, column=col, padx=4, pady=4, sticky="ew")
        parent.columnconfigure(col, weight=1)

        val_label = tk.Label(frame, text=value,
                             font=("Georgia", 18, "bold"),
                             bg=BG_SURF, fg=GOLD_LIGHT)
        val_label.pack()

        tk.Label(frame, text=label,
                 font=("Courier", 7), bg=BG_SURF, fg=DIM_COLOR).pack()

        return val_label

    def _clear_placeholder(self, event):
        if self.wallet_entry.get() == "Enter your OTCoin wallet address...":
            self.wallet_entry.delete(0, "end")

    def _log(self, msg, tag=""):
        self.log.configure(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.log.insert("end", f"[{timestamp}] {msg}\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def toggle_mining(self):
        if not self.mining:
            self.start_mining()
        else:
            self.stop_mining()

    def start_mining(self):
        wallet = self.wallet_entry.get().strip()

        if not wallet or wallet == "Enter your OTCoin wallet address...":
            messagebox.showerror("Error", "Please enter your wallet address!")
            return

        if len(wallet) < 20:
            messagebox.showerror("Error", "Invalid wallet address!")
            return

        self.mining = True
        self.start_time = time.time()
        self.start_btn.configure(
            text="⏹  STOP MINING",
            bg=RED, activebackground="#CC0000"
        )
        self.stat_status.configure(text="MINING", fg=GREEN)

        self._log(f"Starting miner...", "gold")
        self._log(f"Wallet: {wallet[:16]}...", "dim")

        self.mining_thread = threading.Thread(
            target=self._mine_loop, args=(wallet,), daemon=True
        )
        self.mining_thread.start()
        self._update_uptime()

    def stop_mining(self):
        self.mining = False
        self.start_btn.configure(
            text="⛏️  START MINING",
            bg=GOLD, activebackground=GOLD_DARK
        )
        self.stat_status.configure(text="STOPPED", fg=RED)
        self._log("Mining stopped.", "red")

    def _mine_loop(self, wallet_address):
        try:
            # Import blockchain
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from blockchain import Blockchain

            self._log("Loading blockchain...", "dim")
            bc = Blockchain()
            self._log(f"Blockchain loaded! {len(bc.chain)} blocks", "green")

            while self.mining:
                try:
                    new_block = bc.mine_pending_transactions(wallet_address)
                    self.total_blocks += 1
                    self.total_earned = bc.get_balance(wallet_address)

                    # Update UI
                    self.root.after(0, self._update_stats, new_block, bc)
                    self._log(
                        f"✅ Block #{new_block.index} found! "
                        f"+50 OTC | Balance: {self.total_earned:,.1f} OTC",
                        "green"
                    )
                    time.sleep(0.5)

                except Exception as e:
                    self._log(f"Error: {e}", "red")
                    time.sleep(5)

        except ImportError:
            self._log("❌ blockchain.py not found!", "red")
            self._log("Make sure blockchain.py is in the same folder", "dim")
            self.root.after(0, self.stop_mining)

    def _update_stats(self, block, bc):
        self.stat_balance.configure(text=f"{self.total_earned:,.1f}")
        self.stat_blocks.configure(text=str(self.total_blocks))
        self.progress["value"] = bc.total_mined
        self.progress_label.configure(
            text=f"{bc.total_mined:,.0f} / 51,000,000 OTC "
                 f"({bc.total_mined/51000000*100:.4f}%)"
        )

    def _update_uptime(self):
        if self.mining and self.start_time:
            elapsed = int(time.time() - self.start_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            if h > 0:
                uptime = f"{h}h {m}m"
            elif m > 0:
                uptime = f"{m}m {s}s"
            else:
                uptime = f"{s}s"
            self.stat_uptime.configure(text=uptime)
            self.root.after(1000, self._update_uptime)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()

    # Icon (pakai emoji sebagai fallback)
    try:
        root.iconbitmap("otcoin.ico")
    except:
        pass

    app = OTCoinMinerApp(root)
    root.mainloop()
