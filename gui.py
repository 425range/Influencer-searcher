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
        self.title("Influencer Discovery PoC v0.8")
        self.geometry("1120x900")
        self.minsize(980, 760)

        # -----------------------------
        # Visual theme
        # -----------------------------
        self.COLORS = {
            "bg": "#F3F6FA",
            "card": "#FFFFFF",
            "header": "#172554",
            "primary": "#2563EB",
            "primary_hover": "#1D4ED8",
            "success": "#059669",
            "success_hover": "#047857",
            "danger_soft": "#FFF1F2",
            "warning_soft": "#FFF7ED",
            "info_soft": "#EFF6FF",
            "input": "#FFFFFF",
            "border": "#CBD5E1",
            "text": "#111827",
            "muted": "#64748B",
            "log_bg": "#0F172A",
            "log_fg": "#E2E8F0",
        }
        self.configure(bg=self.COLORS["bg"])
        self._setup_styles()

        self.config_path = DEFAULT_CONFIG
        self.cfg = {}
        self.running = False
        self.log_queue = queue.Queue()

        self._build_ui()
        self.load_config(self.config_path)
        self.after(100, self._drain_log_queue)

    def _setup_styles(self):
        c = self.COLORS
        style = ttk.Style(self)

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            ".",
            font=("Segoe UI", 10),
            background=c["bg"],
            foreground=c["text"],
        )

        style.configure("App.TFrame", background=c["bg"])
        style.configure("Card.TFrame", background=c["card"])
        style.configure(
            "Card.TLabelframe",
            background=c["card"],
            bordercolor=c["border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=c["card"],
            foreground=c["text"],
            font=("Segoe UI", 10, "bold"),
        )

        style.configure(
            "TLabel",
            background=c["bg"],
            foreground=c["text"],
        )
        style.configure(
            "Card.TLabel",
            background=c["card"],
            foreground=c["text"],
        )
        style.configure(
            "Muted.Card.TLabel",
            background=c["card"],
            foreground=c["muted"],
        )
        style.configure(
            "Section.Card.TLabel",
            background=c["card"],
            foreground=c["header"],
            font=("Segoe UI", 11, "bold"),
        )

        style.configure(
            "TEntry",
            fieldbackground=c["input"],
            foreground=c["text"],
            insertcolor=c["text"],
            bordercolor=c["border"],
            lightcolor=c["border"],
            darkcolor=c["border"],
            padding=(8, 6),
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", c["primary"])],
            lightcolor=[("focus", c["primary"])],
            darkcolor=[("focus", c["primary"])],
        )

        style.configure(
            "Primary.TButton",
            background=c["primary"],
            foreground="#FFFFFF",
            bordercolor=c["primary"],
            padding=(14, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[
                ("active", c["primary_hover"]),
                ("pressed", c["primary_hover"]),
                ("disabled", "#93C5FD"),
            ],
            foreground=[("disabled", "#EFF6FF")],
        )

        style.configure(
            "Success.TButton",
            background=c["success"],
            foreground="#FFFFFF",
            bordercolor=c["success"],
            padding=(12, 7),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Success.TButton",
            background=[("active", c["success_hover"]), ("pressed", c["success_hover"])],
        )

        style.configure(
            "Secondary.TButton",
            background="#FFFFFF",
            foreground=c["text"],
            bordercolor=c["border"],
            padding=(11, 7),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#F8FAFC"), ("pressed", "#E2E8F0")],
            bordercolor=[("active", "#94A3B8")],
        )

        style.configure(
            "TCheckbutton",
            background=c["card"],
            foreground=c["text"],
        )

        style.configure(
            "TNotebook",
            background=c["bg"],
            borderwidth=0,
            tabmargins=(0, 4, 0, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background="#E2E8F0",
            foreground="#475569",
            padding=(15, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#FFFFFF"), ("active", "#DBEAFE")],
            foreground=[("selected", c["primary"]), ("active", c["header"])],
        )

        style.configure(
            "Status.TLabel",
            background=c["info_soft"],
            foreground=c["header"],
            padding=(10, 5),
            font=("Segoe UI", 9, "bold"),
        )

    def _build_ui(self):
        c = self.COLORS

        # Header
        header = tk.Frame(self, bg=c["header"], height=74)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        title_box = tk.Frame(header, bg=c["header"])
        title_box.pack(side="left", padx=20, pady=13)
        tk.Label(
            title_box,
            text="Influencer Discovery",
            bg=c["header"],
            fg="#FFFFFF",
            font=("Segoe UI", 20, "bold"),
        ).pack(side="left")
        tk.Label(
            title_box,
            text="  v0.8 GUI",
            bg=c["header"],
            fg="#BFDBFE",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", pady=(7, 0))

        header_actions = tk.Frame(header, bg=c["header"])
        header_actions.pack(side="right", padx=16, pady=16)
        ttk.Button(
            header_actions,
            text="설정 불러오기",
            style="Secondary.TButton",
            command=self.choose_config,
        ).pack(side="right", padx=4)
        ttk.Button(
            header_actions,
            text="설정 저장",
            style="Secondary.TButton",
            command=self.save_config,
        ).pack(side="right", padx=4)

        # ----------------------------------------------------------
        # Bottom area is packed BEFORE the notebook.
        # This guarantees that Run / Result buttons and the log
        # remain visible even when a tab contains many settings.
        # ----------------------------------------------------------
        bottom = tk.Frame(self, bg=c["bg"])
        bottom.pack(side="bottom", fill="x", padx=16, pady=(0, 12))

        # Actions
        action = ttk.Frame(bottom, padding=(12, 9), style="Card.TFrame")
        action.pack(fill="x", pady=(6, 8))

        self.run_button = ttk.Button(
            action,
            text="▶  분석 시작",
            style="Primary.TButton",
            command=self.start_analysis,
        )
        self.run_button.pack(side="left")

        ttk.Button(
            action,
            text="결과 Excel 열기",
            style="Success.TButton",
            command=self.open_excel,
        ).pack(side="left", padx=(10, 6))

        ttk.Button(
            action,
            text="결과 폴더 열기",
            style="Secondary.TButton",
            command=self.open_output_folder,
        ).pack(side="left")

        self.status_var = tk.StringVar(value="준비")
        ttk.Label(
            action,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).pack(side="right")

        # Log
        log_frame = ttk.LabelFrame(
            bottom,
            text="실행 로그",
            padding=8,
            style="Card.TLabelframe",
        )
        log_frame.pack(fill="both")

        self.log = tk.Text(
            log_frame,
            height=9,
            wrap="word",
            state="disabled",
            bg=c["log_bg"],
            fg=c["log_fg"],
            insertbackground="#FFFFFF",
            selectbackground="#334155",
            relief="flat",
            padx=10,
            pady=8,
            font=("Consolas", 9),
        )
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Tabs take only the remaining center area.
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(
            side="top",
            fill="both",
            expand=True,
            padx=16,
            pady=(14, 2),
        )

        self.tab_campaign_outer = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_target_outer = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_content_outer = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_visual_outer = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_performance_outer = ttk.Frame(self.notebook, style="Card.TFrame")

        self.notebook.add(self.tab_campaign_outer, text="캠페인 / Discovery")
        self.notebook.add(self.tab_target_outer, text="타겟 / 제외")
        self.notebook.add(self.tab_content_outer, text="Content 유사도")
        self.notebook.add(self.tab_visual_outer, text="Visual")
        self.notebook.add(self.tab_performance_outer, text="Reel / 광고 성과")

        self.tab_campaign = self._make_scrollable_tab(self.tab_campaign_outer)
        self.tab_target = self._make_scrollable_tab(self.tab_target_outer)
        self.tab_content = self._make_scrollable_tab(self.tab_content_outer)
        self.tab_visual = self._make_scrollable_tab(self.tab_visual_outer)
        self.tab_performance = self._make_scrollable_tab(self.tab_performance_outer)

        self._build_campaign_tab()
        self._build_target_tab()
        self._build_content_tab()
        self._build_visual_tab()
        self._build_performance_tab()


    def _make_scrollable_tab(self, parent):
        """
        Return an inner ttk.Frame placed inside a vertically scrollable canvas.
        Mouse wheel scrolling works while the pointer is over the tab.
        """
        c = self.COLORS

        container = ttk.Frame(parent, style="Card.TFrame")
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            container,
            bg=c["card"],
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas, padding=18, style="Card.TFrame")
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _update_scrollregion(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _fit_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        inner.bind("<Configure>", _update_scrollregion)
        canvas.bind("<Configure>", _fit_width)

        def _on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(_event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(_event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        inner.bind("<Enter>", _bind_mousewheel)
        inner.bind("<Leave>", _unbind_mousewheel)

        return inner

    def _entry(self, parent, row, label, var, width=28, help_text=None):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(
            row=row, column=0, sticky="w", pady=7, padx=(0, 14)
        )
        ent = ttk.Entry(parent, textvariable=var, width=width)
        ent.grid(row=row, column=1, sticky="ew", pady=7, ipady=1)
        if help_text:
            ttk.Label(
                parent,
                text=help_text,
                style="Muted.Card.TLabel",
                wraplength=300,
            ).grid(row=row, column=2, sticky="w", padx=12)
        return ent

    def _text_area(self, parent, row, label, height=5, help_text=None, tone="normal"):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(
            row=row, column=0, sticky="nw", pady=7, padx=(0, 14)
        )

        bg = self.COLORS["input"]
        if tone == "danger":
            bg = self.COLORS["danger_soft"]
        elif tone == "warning":
            bg = self.COLORS["warning_soft"]
        elif tone == "info":
            bg = self.COLORS["info_soft"]

        txt = tk.Text(
            parent,
            height=height,
            width=44,
            wrap="word",
            bg=bg,
            fg=self.COLORS["text"],
            insertbackground=self.COLORS["text"],
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=self.COLORS["border"],
            highlightcolor=self.COLORS["primary"],
            padx=8,
            pady=7,
            font=("Segoe UI", 10),
        )
        txt.grid(row=row, column=1, sticky="nsew", pady=7)

        if help_text:
            ttk.Label(
                parent,
                text=help_text,
                style="Muted.Card.TLabel",
                wraplength=300,
            ).grid(row=row, column=2, sticky="nw", padx=12, pady=8)
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
        self.search_queries = self._text_area(f, r, "후보 검색 문구", 5, "Google에서 Instagram 후보 프로필을 추가 발견할 때 사용"); r += 1

        ttk.Checkbutton(f, text="키워드 검색 사용", variable=self.use_keyword_search, style="TCheckbutton").grid(row=r, column=1, sticky="w", pady=5); r += 1
        self._entry(f, r, "최소 팔로워", self.min_followers, help_text="예: 30000"); r += 1
        self._entry(f, r, "최대 팔로워", self.max_followers, help_text="예: 500000"); r += 1
        self._entry(f, r, "추천 확장 Depth", self.seed_depth, help_text="1=직접 추천, 2=추천의 추천"); r += 1
        self._entry(f, r, "계정당 Related 최대", self.max_related); r += 1
        self._entry(f, r, "Seed 후보 최대", self.max_seed_candidates); r += 1

    def _build_target_tab(self):
        f = self.tab_target
        f.columnconfigure(1, weight=1)

        self.include_keywords = self._text_area(f, 0, "포함 키워드", 6, "카테고리 적합도 및 후보 평가에 사용", tone="info")
        self.hard_exclude_keywords = self._text_area(f, 1, "Hard 제외 키워드", 6, "매칭 시 후보에서 즉시 제외", tone="danger")
        self.soft_exclude_keywords = self._text_area(f, 2, "Soft 제외 키워드", 5, "후보는 유지하지만 점수 감점", tone="warning")

        self.soft_penalty = tk.StringVar()
        self.hard_category_threshold = tk.StringVar()
        self.gender_target_display = tk.StringVar(value="전체")
        self._entry(f, 3, "Soft 제외 감점", self.soft_penalty, help_text="0~1, 예: 0.10")
        self.hard_exclude_categories = self._text_area(f, 4, "Hard 제외 카테고리", 4, "예: parenting")
        self._entry(f, 5, "카테고리 제외 기준", self.hard_category_threshold, help_text="예: 0.20")

        ttk.Separator(f).grid(row=6, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(f, text="크리에이터 성별 필터", style="Section.Card.TLabel").grid(row=7, column=0, sticky="w", pady=7, padx=(0, 14))
        self.gender_combo = ttk.Combobox(
            f,
            textvariable=self.gender_target_display,
            values=["전체", "여성 중심", "남성 중심"],
            state="readonly",
            width=22,
        )
        self.gender_combo.grid(row=7, column=1, sticky="w", pady=7)
        ttk.Label(
            f,
            text="Bio/Caption의 명시적 자기소개 신호만 사용합니다. 애매한 계정은 유지합니다.",
            style="Muted.Card.TLabel",
            wraplength=320,
        ).grid(row=7, column=2, sticky="w", padx=12)

        ttk.Separator(f).grid(row=8, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(f, text="Creator Target Gate", style="Section.Card.TLabel").grid(row=9, column=0, columnspan=2, sticky="w")

        self.creator_gate_enabled = tk.BooleanVar(value=True)
        self.min_visual_reference = tk.StringVar()
        self.min_visual_median = tk.StringVar()
        self.min_topic_similarity = tk.StringVar()
        self.min_target_fit = tk.StringVar()
        self.negative_margin_reject = tk.StringVar()

        ttk.Checkbutton(
            f,
            text="Reference 기반 Creator Target Gate 사용",
            variable=self.creator_gate_enabled,
        ).grid(row=10, column=1, sticky="w", pady=7)

        self._entry(f, 11, "최소 Visual Reference", self.min_visual_reference, help_text="기본 0.89")
        self._entry(f, 12, "최소 Visual 게시물 중앙값", self.min_visual_median, help_text="기본 0.82")
        self._entry(f, 13, "최소 Topic Similarity", self.min_topic_similarity, help_text="기본 0.50")
        self._entry(f, 14, "최소 Creator Target Fit", self.min_target_fit, help_text="기본 0.52")
        self._entry(f, 15, "Negative Reference 마진", self.negative_margin_reject, help_text="기본 -0.02")

        ttk.Label(
            f,
            text="얼굴 성별을 판별하지 않습니다. Positive/Negative Reference와 계정 전체 Visual·Topic 패턴을 비교해 타깃 적합도를 판단합니다.",
            style="Muted.Card.TLabel",
            wraplength=720,
        ).grid(row=16, column=0, columnspan=3, sticky="w", pady=(12, 0))

    def _build_content_tab(self):
        f = self.tab_content
        f.columnconfigure(1, weight=1)

        self.text_enabled = tk.BooleanVar(value=True)
        self.text_model = tk.StringVar()
        self.text_recent_posts = tk.StringVar()
        self.text_include_ads = tk.BooleanVar(value=False)
        self.text_include_bio = tk.BooleanVar(value=True)
        self.caption_weight = tk.StringVar()
        self.hashtag_weight = tk.StringVar()
        self.text_batch_size = tk.StringVar()
        self.stop_hashtags = None
        self.reference_top_k = tk.StringVar()
        self.negative_references = None
        self.rank_visual_weight = tk.StringVar()
        self.rank_topic_weight = tk.StringVar()
        self.rank_caption_weight = tk.StringVar()
        self.rank_hashtag_weight = tk.StringVar()
        self.rank_graph_weight = tk.StringVar()
        self.min_combined_similarity = tk.StringVar()

        ttk.Checkbutton(f, text="Caption / Hashtag 유사도 분석 사용", variable=self.text_enabled).grid(row=0, column=1, sticky="w", pady=7)
        self._entry(f, 1, "Text 모델", self.text_model, width=42, help_text="로컬 다국어 임베딩 모델")
        self._entry(f, 2, "최근 게시물 N개", self.text_recent_posts, help_text="이미 Profile Scraper로 가져온 caption을 재사용")
        ttk.Checkbutton(f, text="광고 게시물도 Content 유사도에 포함", variable=self.text_include_ads).grid(row=3, column=1, sticky="w", pady=6)
        ttk.Checkbutton(f, text="프로필 Bio 포함", variable=self.text_include_bio).grid(row=4, column=1, sticky="w", pady=6)
        self._entry(f, 5, "Caption 가중치", self.caption_weight, help_text="예: 0.8")
        self._entry(f, 6, "Hashtag 가중치", self.hashtag_weight, help_text="예: 0.2")
        self._entry(f, 7, "Text Batch Size", self.text_batch_size, help_text="CPU면 8~16 권장")
        self.stop_hashtags = self._text_area(f, 8, "무시할 Hashtag", 5, "# 없이 입력. 광고/범용 태그를 비교에서 제외", tone="warning")

        ttk.Separator(f).grid(row=9, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(f, text="Reference Set + Dynamic Ranking", style="Section.Card.TLabel").grid(row=10, column=0, columnspan=2, sticky="w")
        self._entry(f, 11, "가까운 Reference Top K", self.reference_top_k, help_text="예: 2 → 가장 가까운 Positive Reference 2명 평균")
        self.negative_references = self._text_area(
            f, 12, "Negative Reference (선택)", 4,
            "마케터가 '타깃 아님'으로 판단한 계정. Discovery에는 사용하지 않고 비교 기준으로만 사용",
            tone="warning",
        )
        self._entry(f, 13, "Visual 가중치", self.rank_visual_weight, help_text="기본 0.60")
        self._entry(f, 14, "Topic Profile 가중치", self.rank_topic_weight, help_text="기본 0.25")
        self._entry(f, 15, "Hashtag 가중치", self.rank_hashtag_weight, help_text="기본 0.10")
        self._entry(f, 16, "Graph 가중치", self.rank_graph_weight, help_text="기본 0.05")
        self._entry(f, 17, "Raw Caption 가중치", self.rank_caption_weight, help_text="기본 0.00. 진단값만 유지")
        self._entry(f, 18, "최소 통합 유사도", self.min_combined_similarity, help_text="빈칸=제한 없음")

        note = (
            "v0.8은 raw Caption cosine 대신 Topic Profile을 주 Content 신호로 사용합니다. "
            "Caption이 없으면 해당 신호는 0점이 아니라 제외 후 가중치를 재분배합니다. "
            "Negative Reference는 선택사항이며, 이전 결과에서 명확히 타깃이 아니었던 계정을 넣으면 다음 탐색의 분별력이 좋아집니다."
        )
        ttk.Label(f, text=note, style="Muted.Card.TLabel", wraplength=760).grid(row=19, column=0, columnspan=3, sticky="w", pady=(18, 0))

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
        self._entry(f, 4, "Reel 분석 대상 Top N", self.accounts_to_analyze, help_text="Visual + Content 통합 랭킹 상위 몇 명을 상세 분석할지")

        note = (
            "Visual 분석은 기존 Profile Scraper에서 확보한 최근 게시물 대표 이미지를 사용합니다. "
            "Carousel은 게시물당 대표 이미지 1장만 사용합니다."
        )
        ttk.Label(f, text=note, style="Muted.Card.TLabel", wraplength=700).grid(row=5, column=0, columnspan=3, sticky="w", pady=(18, 0))

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
        ttk.Label(f, text="광고주 Commercial Filter", style="Section.Card.TLabel").grid(row=7, column=0, columnspan=2, sticky="w")
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
        txt = c.get("text_similarity", {})
        sim = c.get("similarity_ranking", {})
        ref = c.get("reference_matching", {})
        v = c.get("visual", {})
        p = c.get("performance", {})
        cf = c.get("commercial_filter", {})
        gate = c.get("creator_target_gate", {})

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
        gender_cfg = t.get("gender_filter", {}) or {}
        gender_target = str(gender_cfg.get("target", "all") or "all").lower()
        self.gender_target_display.set({"female": "여성 중심", "male": "남성 중심"}.get(gender_target, "전체"))
        self.creator_gate_enabled.set(bool(gate.get("enabled", True)))
        self.min_visual_reference.set(str(gate.get("min_visual_reference", 0.89)))
        self.min_visual_median.set(str(gate.get("min_visual_median", 0.82)))
        self.min_topic_similarity.set(str(gate.get("min_topic_similarity", 0.50)))
        self.min_target_fit.set(str(gate.get("min_target_fit", 0.52)))
        self.negative_margin_reject.set(str(gate.get("negative_margin_reject", -0.02)))

        self.text_enabled.set(bool(txt.get("enabled", True)))
        self.text_model.set(txt.get("model_name", "intfloat/multilingual-e5-small"))
        self.text_recent_posts.set(str(txt.get("recent_posts", 8)))
        self.text_include_ads.set(bool(txt.get("include_ads", False)))
        self.text_include_bio.set(bool(txt.get("include_bio", True)))
        self.caption_weight.set(str(txt.get("caption_weight", 0.8)))
        self.hashtag_weight.set(str(txt.get("hashtag_weight", 0.2)))
        self.text_batch_size.set(str(txt.get("batch_size", 16)))
        self._set_text(self.stop_hashtags, join_list(txt.get("stop_hashtags", [])))
        rank_weights = sim.get("weights", {}) or {}
        self.reference_top_k.set(str(ref.get("top_k_references", 2)))
        self._set_text(self.negative_references, join_list(ref.get("negative_usernames", [])))
        self.rank_visual_weight.set(str(rank_weights.get("visual", 0.60)))
        self.rank_topic_weight.set(str(rank_weights.get("topic", 0.25)))
        self.rank_caption_weight.set(str(rank_weights.get("caption", 0.00)))
        self.rank_hashtag_weight.set(str(rank_weights.get("hashtag", 0.10)))
        self.rank_graph_weight.set(str(rank_weights.get("graph", 0.05)))
        self.min_combined_similarity.set(
            "" if sim.get("min_combined_similarity") is None
            else str(sim.get("min_combined_similarity"))
        )

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
        c.setdefault("text_similarity", {})
        c.setdefault("similarity_ranking", {})
        c.setdefault("reference_matching", {})
        c.setdefault("visual", {})
        c.setdefault("performance", {})
        c.setdefault("commercial_filter", {})
        c.setdefault("creator_target_gate", {})

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
        gender_map = {"전체": "all", "여성 중심": "female", "남성 중심": "male"}
        gender_target = gender_map.get(self.gender_target_display.get(), "all")
        gender_cfg = t.setdefault("gender_filter", {})
        gender_cfg["enabled"] = gender_target != "all"
        gender_cfg["target"] = gender_target
        gender_cfg.setdefault("bio_weight", 3.0)
        gender_cfg.setdefault("caption_weight", 1.0)
        gender_cfg.setdefault("reject_threshold", 3.0)
        gender_cfg.setdefault("opposite_margin", 2.0)

        gate = c["creator_target_gate"]
        gate["enabled"] = bool(self.creator_gate_enabled.get())
        gate["min_visual_reference"] = float(self.min_visual_reference.get())
        gate["min_visual_median"] = float(self.min_visual_median.get())
        gate["min_topic_similarity"] = float(self.min_topic_similarity.get())
        gate["min_target_fit"] = float(self.min_target_fit.get())
        gate["negative_margin_reject"] = float(self.negative_margin_reject.get())
        gate.setdefault("reject_low_visual_pair", True)

        txt = c["text_similarity"]
        txt["enabled"] = bool(self.text_enabled.get())
        txt["model_name"] = self.text_model.get().strip()
        txt["recent_posts"] = int(self.text_recent_posts.get())
        txt["include_ads"] = bool(self.text_include_ads.get())
        txt["include_bio"] = bool(self.text_include_bio.get())
        txt["caption_weight"] = float(self.caption_weight.get())
        txt["hashtag_weight"] = float(self.hashtag_weight.get())
        txt["batch_size"] = int(self.text_batch_size.get())
        txt.setdefault("max_length", 512)
        txt.setdefault("cache_path", "cache/text_embeddings.pt")
        txt["stop_hashtags"] = [x.lstrip("#") for x in split_list(self.stop_hashtags.get("1.0", "end"))]

        ref = c["reference_matching"]
        ref["top_k_references"] = int(self.reference_top_k.get())
        ref["negative_usernames"] = split_list(self.negative_references.get("1.0", "end"))

        sim = c["similarity_ranking"]
        sim["weights"] = {
            "visual": float(self.rank_visual_weight.get()),
            "topic": float(self.rank_topic_weight.get()),
            "hashtag": float(self.rank_hashtag_weight.get()),
            "graph": float(self.rank_graph_weight.get()),
            "caption": float(self.rank_caption_weight.get()),
        }
        sim["min_combined_similarity"] = parse_optional_float(self.min_combined_similarity.get())

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
        if txt["recent_posts"] < 1:
            raise ValueError("Content 비교 게시물 수는 1 이상이어야 합니다.")
        if txt["caption_weight"] < 0 or txt["hashtag_weight"] < 0 or (txt["caption_weight"] + txt["hashtag_weight"]) <= 0:
            raise ValueError("Caption/Hashtag 가중치를 확인하세요.")
        if ref["top_k_references"] < 1:
            raise ValueError("Reference Top K는 1 이상이어야 합니다.")
        for name in ("min_visual_reference", "min_visual_median", "min_topic_similarity", "min_target_fit"):
            if not 0 <= float(gate[name]) <= 1:
                raise ValueError(f"{name} 값은 0~1 사이여야 합니다.")
        rank_weights = sim["weights"]
        if any(v < 0 for v in rank_weights.values()) or sum(rank_weights.values()) <= 0:
            raise ValueError("통합 랭킹 가중치를 확인하세요.")
        if sim["min_combined_similarity"] is not None and not 0 <= sim["min_combined_similarity"] <= 1:
            raise ValueError("최소 통합 유사도는 0~1 사이 값이어야 합니다.")
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
        value = self.cfg.get("output", {}).get("excel_path", "output/candidates_v06.xlsx")
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
