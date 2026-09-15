from __future__ import annotations

import os
import queue
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import yaml

from main import main as run_pipeline

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "config" / "campaign.yaml"


def split_list(value: str) -> list[str]:
    values = []
    for line in value.replace(",", "\n").splitlines():
        item = line.strip()
        if item:
            values.append(item)
    return values


def join_list(values) -> str:
    return "\n".join(str(x) for x in (values or []))


class QueueWriter:
    def __init__(self, q: queue.Queue):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(text)

    def flush(self):
        pass


class App(tk.Tk):
    """Non-technical MVP GUI.

    Only campaign inputs are visible. Search depth, model weights, gate thresholds,
    Actor ids, batch sizes and billing constants remain in campaign.yaml as hidden
    defaults so they can be tuned later without exposing them to end users.
    """

    def __init__(self):
        super().__init__()
        self.title("Influencer Discovery v0.9.2")
        self.geometry("900x820")
        self.minsize(820, 720)

        self.COLORS = {
            "bg": "#F3F6FA",
            "card": "#FFFFFF",
            "header": "#172554",
            "primary": "#2563EB",
            "primary_hover": "#1D4ED8",
            "success": "#059669",
            "border": "#CBD5E1",
            "text": "#111827",
            "muted": "#64748B",
            "log_bg": "#0F172A",
            "log_fg": "#E2E8F0",
            "info": "#EFF6FF",
        }
        self.configure(bg=self.COLORS["bg"])
        self._setup_styles()

        self.config_path = DEFAULT_CONFIG
        self.cfg = {}
        self.running = False
        self.log_queue = queue.Queue()

        self._build_ui()
        self.load_config()
        self.after(100, self._drain_log_queue)

    def _setup_styles(self):
        c = self.COLORS
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=("Segoe UI", 10), background=c["bg"], foreground=c["text"])
        style.configure("Card.TFrame", background=c["card"])
        style.configure("Card.TLabel", background=c["card"], foreground=c["text"])
        style.configure("Muted.Card.TLabel", background=c["card"], foreground=c["muted"])
        style.configure(
            "Card.TLabelframe",
            background=c["card"],
            bordercolor=c["border"],
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=c["card"],
            foreground=c["header"],
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "TEntry",
            fieldbackground="#FFFFFF",
            bordercolor=c["border"],
            padding=(8, 6),
        )
        style.configure(
            "Primary.TButton",
            background=c["primary"],
            foreground="#FFFFFF",
            bordercolor=c["primary"],
            padding=(15, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Primary.TButton", background=[("active", c["primary_hover"])])
        style.configure(
            "Success.TButton",
            background=c["success"],
            foreground="#FFFFFF",
            padding=(12, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("Secondary.TButton", background="#FFFFFF", padding=(12, 8))

    def _build_ui(self):
        c = self.COLORS

        header = tk.Frame(self, bg=c["header"], height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Influencer Discovery",
            bg=c["header"],
            fg="#FFFFFF",
            font=("Segoe UI", 20, "bold"),
        ).pack(side="left", padx=22, pady=18)
        tk.Label(
            header,
            text="v0.9.2 · 간편 모드",
            bg=c["header"],
            fg="#BFDBFE",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", pady=(25, 0))

        outer = tk.Frame(self, bg=c["bg"])
        outer.pack(fill="both", expand=True, padx=16, pady=14)

        info = tk.Frame(outer, bg=c["info"], bd=0)
        info.pack(fill="x", pady=(0, 10))
        tk.Label(
            info,
            text=(
                "레퍼런스 계정과 해시태그만 입력하면 됩니다. "
                "검색 깊이, 가중치, 모델 설정은 자동으로 적용됩니다."
            ),
            bg=c["info"],
            fg=c["header"],
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=10,
        ).pack(anchor="w")

        form = ttk.LabelFrame(outer, text="검색 조건", padding=16, style="Card.TLabelframe")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self.campaign_name = tk.StringVar()
        self.product = tk.StringVar()
        self.target_candidates = tk.StringVar(value="100")
        self.min_followers = tk.StringVar(value="30000")
        self.max_followers = tk.StringVar(value="500000")

        self._entry(form, 0, "캠페인 이름", self.campaign_name, "결과 파일을 구분하기 위한 이름")
        self._entry(form, 1, "제품 / 캠페인", self.product, "예: 임산부 멀티비타민, 여행 앱")

        ttk.Label(form, text="레퍼런스 계정", style="Card.TLabel").grid(row=2, column=0, sticky="nw", pady=(12, 4), padx=(0, 12))
        self.seed_usernames = tk.Text(form, height=5, wrap="word", relief="solid", bd=1, font=("Segoe UI", 10))
        self.seed_usernames.grid(row=2, column=1, sticky="ew", pady=(12, 4))
        ttk.Label(
            form,
            text="한 줄에 하나씩 입력하세요. 비워두면 관련 추천 계정 검색은 생략됩니다.",
            style="Muted.Card.TLabel",
        ).grid(row=3, column=1, sticky="w", pady=(0, 8))

        ttk.Label(form, text="검색 해시태그", style="Card.TLabel").grid(row=4, column=0, sticky="nw", pady=(8, 4), padx=(0, 12))
        self.hashtags = tk.Text(form, height=6, wrap="word", relief="solid", bd=1, font=("Segoe UI", 10))
        self.hashtags.grid(row=4, column=1, sticky="ew", pady=(8, 4))
        ttk.Label(
            form,
            text="예: 올영세일, 임산부영양제, 유럽여행. # 기호는 없어도 됩니다.",
            style="Muted.Card.TLabel",
        ).grid(row=5, column=1, sticky="w", pady=(0, 8))

        row6 = ttk.Frame(form, style="Card.TFrame")
        row6.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for i in range(3):
            row6.columnconfigure(i, weight=1)
        self._compact_entry(row6, 0, "목표 후보 수", self.target_candidates, "예: 100")
        self._compact_entry(row6, 1, "최소 팔로워", self.min_followers, "예: 30000")
        self._compact_entry(row6, 2, "최대 팔로워", self.max_followers, "예: 500000")

        billing = ttk.LabelFrame(outer, text="자동 검색 방식", padding=12, style="Card.TLabelframe")
        billing.pack(fill="x", pady=(10, 0))
        ttk.Label(
            billing,
            text=(
                "관련 추천 계정은 전체 목표의 일부만 우선 수집하고, "
                "해시태그 검색은 팔로워 조건에 맞는 후보 수가 부족하면 자동으로 더 검색합니다. "
                "모든 후보는 삭제하지 않고 Excel에 남깁니다."
            ),
            style="Card.TLabel",
            wraplength=820,
            justify="left",
        ).pack(anchor="w")

        actions = ttk.Frame(outer, padding=(0, 12, 0, 6))
        actions.pack(fill="x")
        self.run_button = ttk.Button(actions, text="▶  인플루언서 찾기", style="Primary.TButton", command=self.start_analysis)
        self.run_button.pack(side="left")
        ttk.Button(actions, text="결과 Excel 열기", style="Success.TButton", command=self.open_excel).pack(side="left", padx=(10, 6))
        ttk.Button(actions, text="결과 폴더", style="Secondary.TButton", command=self.open_output_folder).pack(side="left")
        self.status_var = tk.StringVar(value="준비")
        ttk.Label(actions, textvariable=self.status_var).pack(side="right")

        log_frame = ttk.LabelFrame(outer, text="진행 상황", padding=8, style="Card.TLabelframe")
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(
            log_frame,
            height=12,
            wrap="word",
            state="disabled",
            bg=c["log_bg"],
            fg=c["log_fg"],
            relief="flat",
            padx=10,
            pady=8,
            font=("Consolas", 9),
        )
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _entry(self, parent, row, label, var, hint=""):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=7, padx=(0, 12))
        box = ttk.Frame(parent, style="Card.TFrame")
        box.grid(row=row, column=1, sticky="ew", pady=7)
        box.columnconfigure(0, weight=1)
        ttk.Entry(box, textvariable=var).grid(row=0, column=0, sticky="ew")
        if hint:
            ttk.Label(box, text=hint, style="Muted.Card.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))

    def _compact_entry(self, parent, col, label, var, hint=""):
        box = ttk.Frame(parent, style="Card.TFrame")
        box.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))
        ttk.Label(box, text=label, style="Card.TLabel").pack(anchor="w")
        ttk.Entry(box, textvariable=var).pack(fill="x", pady=(4, 2))
        ttk.Label(box, text=hint, style="Muted.Card.TLabel").pack(anchor="w")

    def load_config(self):
        with self.config_path.open("r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f) or {}
        c = self.cfg
        d = c.setdefault("discovery", {})
        flt = c.setdefault("filters", {})
        camp = c.setdefault("campaign", {})

        self.campaign_name.set(str(camp.get("name", "")))
        self.product.set(str(camp.get("product", "")))
        self.target_candidates.set(str(d.get("target_candidates", 100)))
        self.min_followers.set(str(flt.get("min_followers", 30000)))
        self.max_followers.set(str(flt.get("max_followers", 500000)))

        self.seed_usernames.delete("1.0", "end")
        self.seed_usernames.insert("1.0", join_list(d.get("seed_usernames", [])))
        self.hashtags.delete("1.0", "end")
        self.hashtags.insert("1.0", join_list(d.get("hashtags", [])))

    def _apply_to_cfg(self):
        c = self.cfg
        c.setdefault("campaign", {})
        c.setdefault("discovery", {})
        c.setdefault("filters", {})
        c.setdefault("output", {})
        d = c["discovery"]
        flt = c["filters"]

        c["campaign"]["name"] = self.campaign_name.get().strip() or "Influencer Search"
        c["campaign"]["product"] = self.product.get().strip()

        seeds = [x.lstrip("@") for x in split_list(self.seed_usernames.get("1.0", "end"))]
        tags = [x.lstrip("#") for x in split_list(self.hashtags.get("1.0", "end"))]
        target = int(self.target_candidates.get())
        min_f = int(self.min_followers.get())
        max_f = int(self.max_followers.get())

        if target < 1:
            raise ValueError("목표 후보 수는 1명 이상이어야 합니다.")
        if min_f < 0 or max_f < min_f:
            raise ValueError("팔로워 범위를 확인하세요.")
        if not seeds and not tags:
            raise ValueError("레퍼런스 계정 또는 검색 해시태그를 하나 이상 입력하세요.")

        d["seed_usernames"] = seeds
        d["hashtags"] = tags
        d["target_candidates"] = target
        d["use_related_search"] = bool(seeds)
        d["use_hashtag_search"] = bool(tags)
        d["use_keyword_search"] = False

        # Hidden defaults: intentionally not exposed in the GUI.
        d.setdefault("related_share_when_both", 0.30)
        d.setdefault("seed_expansion_depth", 2)
        d.setdefault("max_related_per_profile", 20)
        d.setdefault("use_related_fallback", True)
        d.setdefault("related_fallback_actor_id", "instagram-scraper/instagram-related-profiles")
        d.setdefault("hashtag_actor_id", "dami_studio/instagram-hashtag-scraper")
        d.setdefault("hashtag_initial_results_limit", 50)
        d.setdefault("hashtag_growth_factor", 2.0)
        d.setdefault("hashtag_max_results_limit", 500)
        d.setdefault("hashtag_max_rounds", 4)
        d.setdefault("hashtag_cost_per_result_usd", 0.0004)
        d.setdefault("profile_actor_id", "dami_studio/instagram-profile-scraper")
        d.setdefault("profile_include_latest_posts", True)
        d.setdefault("profile_cost_per_result_usd", 0.0007)
        d.setdefault("hashtag_ad_signal_tags", ["광고", "협찬", "제품제공", "유료광고"])

        flt["min_followers"] = min_f
        flt["max_followers"] = max_f
        flt.setdefault("allow_unknown_followers", False)
        flt.setdefault("include_seed_accounts", False)

        c["output"]["excel_path"] = "output/candidates_v092.xlsx"

    def save_config(self):
        try:
            self._apply_to_cfg()
            with self.config_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(self.cfg, f, allow_unicode=True, sort_keys=False)
            return True
        except Exception as exc:
            messagebox.showerror("입력 확인", str(exc))
            return False

    def start_analysis(self):
        if self.running:
            return
        if not self.save_config():
            return
        if not os.getenv("APIFY_TOKEN"):
            env_file = BASE_DIR / ".env"
            if not env_file.exists():
                messagebox.showwarning("API Key 필요", "프로젝트 루트의 .env에 APIFY_TOKEN이 필요합니다.")
                return

        self.running = True
        self.run_button.configure(state="disabled")
        self.status_var.set("검색 중")
        self._append_log("\n=== Search started ===\n")
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self):
        old_stdout, old_stderr = sys.stdout, sys.stderr
        writer = QueueWriter(self.log_queue)
        try:
            sys.stdout = writer
            sys.stderr = writer
            old_cwd = os.getcwd()
            os.chdir(BASE_DIR)
            try:
                run_pipeline(str(self.config_path))
            finally:
                os.chdir(old_cwd)
            self.log_queue.put("\n=== Search completed ===\n")
            self.after(0, self._run_finished, True, "완료")
        except Exception:
            self.log_queue.put("\n" + traceback.format_exc() + "\n")
            self.after(0, self._run_finished, False, "오류")
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

    def _run_finished(self, success, text):
        self.running = False
        self.run_button.configure(state="normal")
        self.status_var.set(text)
        if success:
            messagebox.showinfo("완료", "검색이 완료되었습니다. 결과 Excel을 확인하세요.")
        else:
            messagebox.showerror("실패", "진행 상황에서 오류 내용을 확인하세요.")

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain_log_queue(self):
        try:
            while True:
                self._append_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

    def _excel_path(self) -> Path:
        value = self.cfg.get("output", {}).get("excel_path", "output/candidates_v092.xlsx")
        p = Path(value)
        return p if p.is_absolute() else BASE_DIR / p

    def open_excel(self):
        path = self._excel_path()
        if not path.exists():
            messagebox.showwarning("결과 없음", f"아직 결과 파일이 없습니다.\n{path}")
            return
        self._open_path(path)

    def open_output_folder(self):
        path = self._excel_path().parent
        path.mkdir(parents=True, exist_ok=True)
        self._open_path(path)

    def _open_path(self, path: Path):
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception as exc:
            messagebox.showerror("열기 실패", str(exc))


if __name__ == "__main__":
    App().mainloop()
