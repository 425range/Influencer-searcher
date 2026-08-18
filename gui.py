from __future__ import annotations

import os
import queue
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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


def parse_optional_int(value: str):
    value = value.strip()
    return None if value == "" else int(value)


def parse_optional_float(value: str):
    value = value.strip()
    return None if value == "" else float(value)


class QueueWriter:
    def __init__(self, q: queue.Queue):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(text)

    def flush(self):
        pass


class ScrollText(tk.Text):
    pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Influencer Discovery PoC v0.5")
        self.geometry("1040x840")
        self.minsize(920, 720)

        self.config_path = DEFAULT_CONFIG
        self.cfg = {}
        self.running = False
        self.log_queue = queue.Queue()

        self._build_ui()
        self.load_config(self.config_path)
        self.after(100, self._drain_log_queue)

    def _build_ui(self):
        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="x")

        ttk.Label(top, text="Influencer Discovery", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(top, text="  v0.5 GUI", font=("Segoe UI", 11)).pack(side="left", pady=(5, 0))

        ttk.Button(top, text="설정 불러오기", command=self.choose_config).pack(side="right", padx=4)
        ttk.Button(top, text="설정 저장", command=self.save_config).pack(side="right", padx=4)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.tab_campaign = ttk.Frame(self.notebook, padding=14)
        self.tab_target = ttk.Frame(self.notebook, padding=14)
        self.tab_visual = ttk.Frame(self.notebook, padding=14)
        self.tab_performance = ttk.Frame(self.notebook, padding=14)

        self.notebook.add(self.tab_campaign, text="캠페인 / Discovery")
        self.notebook.add(self.tab_target, text="타겟 / 제외")
        self.notebook.add(self.tab_visual, text="Visual")
        self.notebook.add(self.tab_performance, text="Reel / 광고 성과")

        self._build_campaign_tab()
        self._build_target_tab()
        self._build_visual_tab()
        self._build_performance_tab()

        action = ttk.Frame(self, padding=(12, 4))
        action.pack(fill="x")

        self.run_button = ttk.Button(action, text="분석 시작", command=self.start_analysis)
        self.run_button.pack(side="left")
        ttk.Button(action, text="결과 Excel 열기", command=self.open_excel).pack(side="left", padx=6)
        ttk.Button(action, text="결과 폴더 열기", command=self.open_output_folder).pack(side="left")

        self.status_var = tk.StringVar(value="준비")
        ttk.Label(action, textvariable=self.status_var).pack(side="right")

        log_frame = ttk.LabelFrame(self, text="실행 로그", padding=8)
        log_frame.pack(fill="both", expand=False, padx=12, pady=(2, 12))

        self.log = tk.Text(log_frame, height=13, wrap="word", state="disabled")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _entry(self, parent, row, label, var, width=28, help_text=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5, padx=(0, 12))
        ent = ttk.Entry(parent, textvariable=var, width=width)
        ent.grid(row=row, column=1, sticky="ew", pady=5)
        if help_text:
            ttk.Label(parent, text=help_text, foreground="#666").grid(row=row, column=2, sticky="w", padx=10)
        return ent

    def _text_area(self, parent, row, label, height=5, help_text=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", pady=6, padx=(0, 12))
        txt = tk.Text(parent, height=height, width=44, wrap="word")
        txt.grid(row=row, column=1, sticky="nsew", pady=6)
        if help_text:
            ttk.Label(parent, text=help_text, foreground="#666", wraplength=290).grid(row=row, column=2, sticky="nw", padx=10, pady=6)
        return txt

    def _build_campaign_tab(self):
        f = self.tab_campaign
        f.columnconfigure(1, weight=1)

        self.campaign_name = tk.StringVar()
        self.product = tk.StringVar()
        self.min_followers = tk.StringVar()
        self.max_followers = tk.StringVar()
        self.seed_depth = tk.StringVar()
        self.max_related = tk.StringVar()
        self.max_seed_candidates = tk.StringVar()
        self.use_keyword_search = tk.BooleanVar(value=True)

        r = 0
        self._entry(f, r, "캠페인명", self.campaign_name); r += 1
        self._entry(f, r, "제품 / 브랜드", self.product); r += 1
        self.seed_usernames = self._text_area(f, r, "레퍼런스 계정", 4, "한 줄에 하나씩 Instagram username 입력"); r += 1
        self.search_queries = self._text_area(f, r, "검색어", 5, "키워드 검색을 사용할 때의 검색 문구"); r += 1

        ttk.Checkbutton(f, text="키워드 검색 사용", variable=self.use_keyword_search).grid(row=r, column=1, sticky="w", pady=5); r += 1
        self._entry(f, r, "최소 팔로워", self.min_followers, help_text="예: 30000"); r += 1
        self._entry(f, r, "최대 팔로워", self.max_followers, help_text="예: 500000"); r += 1
        self._entry(f, r, "추천 확장 Depth", self.seed_depth, help_text="1=직접 추천, 2=추천의 추천"); r += 1
        self._entry(f, r, "계정당 Related 최대", self.max_related); r += 1
        self._entry(f, r, "Seed 후보 최대", self.max_seed_candidates); r += 1

    def _build_target_tab(self):
        f = self.tab_target
        f.columnconfigure(1, weight=1)

        self.include_keywords = self._text_area(f, 0, "포함 키워드", 6, "카테고리 적합도 및 후보 평가에 사용")
        self.hard_exclude_keywords = self._text_area(f, 1, "Hard 제외 키워드", 6, "매칭 시 후보에서 즉시 제외")
        self.soft_exclude_keywords = self._text_area(f, 2, "Soft 제외 키워드", 5, "후보는 유지하지만 점수 감점")

        self.soft_penalty = tk.StringVar()
        self.hard_category_threshold = tk.StringVar()
        self._entry(f, 3, "Soft 제외 감점", self.soft_penalty, help_text="0~1, 예: 0.10")
        self.hard_exclude_categories = self._text_area(f, 4, "Hard 제외 카테고리", 4, "예: parenting")
        self._entry(f, 5, "카테고리 제외 기준", self.hard_category_threshold, help_text="예: 0.20")

    def _build_visual_tab(self):
        f = self.tab_visual
        f.columnconfigure(1, weight=1)

        self.visual_enabled = tk.BooleanVar(value=True)
        self.visual_model = tk.StringVar()
        self.images_per_account = tk.StringVar()
        self.visual_batch_size = tk.StringVar()
        self.accounts_to_analyze = tk.StringVar()

        ttk.Checkbutton(f, text="SigLIP Visual 분석 사용", variable=self.visual_enabled).grid(row=0, column=1, sticky="w", pady=7)
        self._entry(f, 1, "모델", self.visual_model, width=42)
        self._entry(f, 2, "계정당 대표 이미지", self.images_per_account, help_text="최근 서로 다른 게시물 대표 이미지 수")
        self._entry(f, 3, "Batch Size", self.visual_batch_size)
        self._entry(f, 4, "Reel 분석 대상 Top N", self.accounts_to_analyze, help_text="Visual 상위 몇 명에게 상세 성과 크롤링할지")

        note = (
            "Visual 분석은 기존 Profile Scraper에서 확보한 최근 게시물 대표 이미지를 사용합니다. "
            "Carousel은 게시물당 대표 이미지 1장만 사용합니다."
        )
        ttk.Label(f, text=note, foreground="#555", wraplength=700).grid(row=5, column=0, columnspan=3, sticky="w", pady=(18, 0))

    def _build_performance_tab(self):
        f = self.tab_performance
        f.columnconfigure(1, weight=1)

        self.performance_enabled = tk.BooleanVar(value=True)
        self.ad_reels_target = tk.StringVar()
        self.max_reels_to_scan = tk.StringVar()
        self.only_posts_newer_than = tk.StringVar()
        self.skip_pinned_posts = tk.BooleanVar(value=True)
        self.include_shares_count = tk.BooleanVar(value=False)

        self.min_ad_reels = tk.StringVar()
        self.max_ad_reels = tk.StringVar()
        self.max_ad_ratio = tk.StringVar()
        self.reject_no_reel_data = tk.BooleanVar(value=False)

        ttk.Checkbutton(f, text="Reel 광고 성과 분석 사용", variable=self.performance_enabled).grid(row=0, column=1, sticky="w", pady=6)
        self._entry(f, 1, "최근 광고 Reel N개", self.ad_reels_target, help_text="예: 5 → 최근 광고 Reel 5개의 평균/중앙값")
        self._entry(f, 2, "계정당 Reel 최대 탐색", self.max_reels_to_scan, help_text="비용 보호 장치, 예: 30")
        self._entry(f, 3, "최대 조회 기간", self.only_posts_newer_than, help_text='예: 12 months, 6 months')

        ttk.Checkbutton(f, text="고정(Pinned) Reel 제외", variable=self.skip_pinned_posts).grid(row=4, column=1, sticky="w", pady=5)
        ttk.Checkbutton(f, text="공유 수 요청", variable=self.include_shares_count).grid(row=5, column=1, sticky="w", pady=5)

        ttk.Separator(f).grid(row=6, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(f, text="광고주 Commercial Filter", font=("Segoe UI", 10, "bold")).grid(row=7, column=0, columnspan=2, sticky="w")
        self._entry(f, 8, "최소 광고 Reel", self.min_ad_reels, help_text="빈칸 = 제한 없음")
        self._entry(f, 9, "탐색 범위 내 광고 최대", self.max_ad_reels, help_text="빈칸 = 제한 없음")
        self._entry(f, 10, "최대 광고 비율", self.max_ad_ratio, help_text="예: 0.5 = 50%, 빈칸 = 제한 없음")
        ttk.Checkbutton(f, text="Reel 데이터가 없으면 제외", variable=self.reject_no_reel_data).grid(row=11, column=1, sticky="w", pady=5)

    def choose_config(self):
        path = filedialog.askopenfilename(
            title="campaign.yaml 선택",
            initialdir=str((BASE_DIR / "config").resolve()),
            filetypes=[("YAML", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if path:
            self.load_config(Path(path))

    def load_config(self, path: Path):
        try:
            with Path(path).open("r", encoding="utf-8") as f:
                self.cfg = yaml.safe_load(f) or {}
            self.config_path = Path(path)
            self._populate_from_cfg()
            self.status_var.set(f"설정 로드: {self.config_path.name}")
        except Exception as exc:
            messagebox.showerror("설정 오류", str(exc))

    def _set_text(self, widget: tk.Text, value: str):
        widget.delete("1.0", "end")
        widget.insert("1.0", value)

    def _populate_from_cfg(self):
        c = self.cfg
        campaign = c.get("campaign", {})
        d = c.get("discovery", {})
        flt = c.get("filters", {})
        t = c.get("targeting", {})
        v = c.get("visual", {})
        p = c.get("performance", {})
        cf = c.get("commercial_filter", {})

        self.campaign_name.set(campaign.get("name", ""))
        self.product.set(campaign.get("product", ""))
        self._set_text(self.seed_usernames, join_list(d.get("seed_usernames", [])))
        self._set_text(self.search_queries, join_list(d.get("queries", [])))
        self.use_keyword_search.set(bool(d.get("use_keyword_search", True)))
        self.min_followers.set(str(flt.get("min_followers", "")))
        self.max_followers.set(str(flt.get("max_followers", "")))
        self.seed_depth.set(str(d.get("seed_expansion_depth", 1)))
        self.max_related.set(str(d.get("max_related_per_profile", 20)))
        self.max_seed_candidates.set(str(d.get("max_seed_candidates", 120)))

        self._set_text(self.include_keywords, join_list(t.get("include_keywords", [])))
        self._set_text(self.hard_exclude_keywords, join_list(t.get("hard_exclude_keywords", [])))
        self._set_text(self.soft_exclude_keywords, join_list(t.get("soft_exclude_keywords", [])))
        self.soft_penalty.set(str(t.get("soft_exclude_penalty", 0.10)))
        self._set_text(self.hard_exclude_categories, join_list(t.get("hard_exclude_categories", [])))
        self.hard_category_threshold.set(str(t.get("hard_exclude_category_threshold", 0.20)))

        self.visual_enabled.set(bool(v.get("enabled", True)))
        self.visual_model.set(v.get("model_name", "google/siglip2-base-patch16-224"))
        self.images_per_account.set(str(v.get("images_per_account", 6)))
        self.visual_batch_size.set(str(v.get("batch_size", 8)))
        self.accounts_to_analyze.set(str(p.get("accounts_to_analyze", 30)))

        self.performance_enabled.set(bool(p.get("enabled", True)))
        self.ad_reels_target.set(str(p.get("ad_reels_target", 5)))
        self.max_reels_to_scan.set(str(p.get("max_reels_to_scan", 30)))
        self.only_posts_newer_than.set(str(p.get("only_posts_newer_than") or ""))
        self.skip_pinned_posts.set(bool(p.get("skip_pinned_posts", True)))
        self.include_shares_count.set(bool(p.get("include_shares_count", False)))

        self.min_ad_reels.set("" if cf.get("min_ad_reels") is None else str(cf.get("min_ad_reels")))
        self.max_ad_reels.set("" if cf.get("max_ad_reels_in_scan") is None else str(cf.get("max_ad_reels_in_scan")))
        self.max_ad_ratio.set("" if cf.get("max_ad_ratio") is None else str(cf.get("max_ad_ratio")))
        self.reject_no_reel_data.set(bool(cf.get("reject_no_reel_data", False)))

    def _apply_to_cfg(self):
        c = self.cfg
        c.setdefault("campaign", {})
        c.setdefault("discovery", {})
        c.setdefault("filters", {})
        c.setdefault("targeting", {})
        c.setdefault("visual", {})
        c.setdefault("performance", {})
        c.setdefault("commercial_filter", {})

        c["campaign"]["name"] = self.campaign_name.get().strip()
        c["campaign"]["product"] = self.product.get().strip()

        d = c["discovery"]
        d["seed_usernames"] = split_list(self.seed_usernames.get("1.0", "end"))
        d["queries"] = split_list(self.search_queries.get("1.0", "end"))
        d["use_keyword_search"] = bool(self.use_keyword_search.get())
        d["seed_expansion_depth"] = int(self.seed_depth.get())
        d["max_related_per_profile"] = int(self.max_related.get())
        d["max_seed_candidates"] = int(self.max_seed_candidates.get())

        flt = c["filters"]
        flt["min_followers"] = int(self.min_followers.get())
        flt["max_followers"] = int(self.max_followers.get())

        t = c["targeting"]
        t["include_keywords"] = split_list(self.include_keywords.get("1.0", "end"))
        t["hard_exclude_keywords"] = split_list(self.hard_exclude_keywords.get("1.0", "end"))
        t["soft_exclude_keywords"] = split_list(self.soft_exclude_keywords.get("1.0", "end"))
        t["soft_exclude_penalty"] = float(self.soft_penalty.get())
        t["hard_exclude_categories"] = split_list(self.hard_exclude_categories.get("1.0", "end"))
        t["hard_exclude_category_threshold"] = float(self.hard_category_threshold.get())

        v = c["visual"]
        v["enabled"] = bool(self.visual_enabled.get())
        v["model_name"] = self.visual_model.get().strip()
        v["images_per_account"] = int(self.images_per_account.get())
        v["batch_size"] = int(self.visual_batch_size.get())

        p = c["performance"]
        p["enabled"] = bool(self.performance_enabled.get())
        p["accounts_to_analyze"] = int(self.accounts_to_analyze.get())
        p["ad_reels_target"] = int(self.ad_reels_target.get())
        p["max_reels_to_scan"] = int(self.max_reels_to_scan.get())
        p["only_posts_newer_than"] = self.only_posts_newer_than.get().strip() or None
        p["skip_pinned_posts"] = bool(self.skip_pinned_posts.get())
        p["include_shares_count"] = bool(self.include_shares_count.get())

        cf = c["commercial_filter"]
        cf["min_ad_reels"] = parse_optional_int(self.min_ad_reels.get())
        cf["max_ad_reels_in_scan"] = parse_optional_int(self.max_ad_reels.get())
        cf["max_ad_ratio"] = parse_optional_float(self.max_ad_ratio.get())
        cf["reject_no_reel_data"] = bool(self.reject_no_reel_data.get())

        # Basic validation
        if not d["seed_usernames"]:
            raise ValueError("레퍼런스 계정을 최소 1개 입력하세요.")
        if flt["min_followers"] < 0 or flt["max_followers"] < flt["min_followers"]:
            raise ValueError("팔로워 범위를 확인하세요.")
        if p["ad_reels_target"] < 1:
            raise ValueError("최근 광고 Reel N개는 1 이상이어야 합니다.")
        if p["max_reels_to_scan"] < p["ad_reels_target"]:
            raise ValueError("Reel 최대 탐색 수는 광고 Reel 목표 개수 이상이어야 합니다.")
        if cf["max_ad_ratio"] is not None and not 0 <= cf["max_ad_ratio"] <= 1:
            raise ValueError("최대 광고 비율은 0~1 사이 값이어야 합니다.")

    def save_config(self, silent=False):
        try:
            self._apply_to_cfg()
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(self.cfg, f, allow_unicode=True, sort_keys=False)
            self.status_var.set(f"설정 저장: {self.config_path.name}")
            if not silent:
                messagebox.showinfo("저장 완료", f"설정을 저장했습니다.\n{self.config_path}")
            return True
        except Exception as exc:
            messagebox.showerror("설정 확인", str(exc))
            return False

    def start_analysis(self):
        if self.running:
            return
        if not self.save_config(silent=True):
            return

        if not os.getenv("APIFY_TOKEN"):
            env_file = BASE_DIR / ".env"
            if not env_file.exists():
                messagebox.showwarning(
                    "API Key 필요",
                    "현재 테스트 버전은 프로젝트 루트의 .env에 APIFY_TOKEN이 필요합니다.\n"
                    "API Key 입력 UI는 다음 단계에서 추가할 수 있습니다.",
                )
                return

        self.running = True
        self.run_button.configure(state="disabled")
        self.status_var.set("분석 실행 중")
        self._append_log("\n=== Analysis started ===\n")
        thread = threading.Thread(target=self._run_worker, daemon=True)
        thread.start()

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
            self.log_queue.put("\n=== Analysis completed ===\n")
            self.after(0, self._run_finished, True, "완료")
        except Exception:
            self.log_queue.put("\n" + traceback.format_exc() + "\n")
            self.after(0, self._run_finished, False, "오류 발생")
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

    def _run_finished(self, success, text):
        self.running = False
        self.run_button.configure(state="normal")
        self.status_var.set(text)
        if success:
            messagebox.showinfo("분석 완료", "분석이 완료되었습니다. 결과 Excel을 확인하세요.")
        else:
            messagebox.showerror("분석 실패", "실행 로그에서 오류 내용을 확인하세요.")

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
        value = self.cfg.get("output", {}).get("excel_path", "output/candidates_v05.xlsx")
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
    app = App()
    app.mainloop()
