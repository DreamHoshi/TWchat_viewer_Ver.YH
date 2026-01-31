import time
import os
import sys
import json
import tkinter as tk
from tkinter import scrolledtext, Listbox, filedialog, colorchooser
from bs4 import BeautifulSoup
import threading
from collections import OrderedDict
from ctypes import windll
import tkinter.ttk as ttk

# ============================================================
#   PyInstaller 対応：リソースパス取得
# ============================================================
def resource_path(filename):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return filename

# ============================================================
#   設定ファイル（JSON）
# ============================================================
SETTINGS_FILE = "settings.json"

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except:
        print("設定保存エラー")

# ============================================================
#   チャット色設定（HTML色 → (種別, 表示色)）
# ============================================================
chat_colors = OrderedDict({
    "#c8ffc8": ("一般", "white"),
    "#ffffff": ("一般", "white"),
    "#64ff64": ("耳打ち", "green"),
    "#f7b73c": ("チーム", "orange"),
    "#94ddfa": ("クラブ", "cyan"),
    "#ff64ff": ("システム", "#FFD56B"),
    "#c896c8": ("叫ぶ", "violet")
})

chat_order = ["一般", "耳打ち", "チーム", "クラブ", "システム", "叫ぶ"]

EXCLUDE_LABELS = {
    "経験値が": "取得経験値",
    "ルーン経験値が": "取得ルーン経験値",
    "[ELSO": "取得ELSO",
    "ペットが": "ペット取得"
}

EXCLUDE_PATTERNS = list(EXCLUDE_LABELS.keys())

# ============================================================
#   ChatViewer ver3
# ============================================================
class ChatViewerVer3:
    def __init__(self, root):
        self.root = root
        self.root.title("チャットログビューア ver3")
        self.root.iconbitmap(resource_path("zelippi_icon.ico"))
        self.root.geometry("720x600")

        # Notebookタブのスタイル
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "TNotebook.Tab",
            background="#1F2A44",
            foreground="white",
            font=("Meiryo", 10, "bold"),
            padding=[10, 5],
            borderwidth=0
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#3A6EA5")],
            foreground=[("selected", "white")]
        )

        # JSON 読み込み
        self.settings = load_settings()

        # チャット色
        self.chat_display_colors = {}
        for _, (ctype, disp) in chat_colors.items():
            if ctype not in self.chat_display_colors:
                self.chat_display_colors[ctype] = disp

        saved_colors = self.settings.get("chat_display_colors", {})
        for ctype, col in saved_colors.items():
            if ctype in self.chat_display_colors:
                self.chat_display_colors[ctype] = col

        # 除外ログ
        self.exclude_options = {}
        saved_exclude = self.settings.get("exclude_options", {})
        for pat in EXCLUDE_PATTERNS:
            self.exclude_options[pat] = tk.BooleanVar(
                value=saved_exclude.get(pat, False)
            )

        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        # ビュータブ
        self.tab_view = tk.Frame(self.notebook, bg="#0D1117")
        self.notebook.add(self.tab_view, text="ビュー")

        # 設定タブ（スクロール対応）
        self.tab_settings = tk.Frame(self.notebook, bg="#0D1117")
        self.notebook.add(self.tab_settings, text="設定")

        # 共通状態
        self.base_folder = self.settings.get(
            "folder", "C:\\Nexon\\TalesWeaver\\ChatLog"
        )
        self.monitoring = False
        self.messages = []

        # NG/SP
        self.ng_words = self.settings.get("ng_words", [])
        self.sp_words = self.settings.get("sp_words", [])

        # 表示切替
        self.show_time = tk.BooleanVar(value=self.settings.get("show_time", True))
        self.show_label = tk.BooleanVar(value=self.settings.get("show_label", True))
        self.remember_state = tk.BooleanVar(value=self.settings.get("remember_state", False))

        # フィルタ
        self.filters = {}
        saved_filters = self.settings.get("filters", {})
        for chat_type in chat_order:
            self.filters[chat_type] = tk.BooleanVar(
                value=saved_filters.get(chat_type, True)
            )

        # compact
        self.compact_mode = tk.BooleanVar(value=False)
        self.compact_window = None
        self.click_through_var = tk.BooleanVar(value=False)

        # UI構築
        self.build_view_tab()
        self.build_settings_tab()

        self.status_label.config(text="停止中", fg="#3A6EA5")

    # ============================================================
    #   ビュータブ
    # ============================================================
    def build_view_tab(self):
        main_frame = self.tab_view

        # 上部
        top_frame = tk.Frame(main_frame, bg="#0D1117")
        top_frame.pack(fill="x", pady=5)

        tk.Button(
            top_frame, text="読み込み開始", command=self.start_monitor,
            bg="#1F2A44", fg="white"
        ).pack(side="left", padx=5)

        tk.Button(
            top_frame, text="停止", command=self.stop_monitor,
            bg="#1F2A44", fg="white"
        ).pack(side="left", padx=5)

        self.status_label = tk.Label(
            top_frame,
            text="停止中",
            bg="#0D1117",
            fg="#3A6EA5",
            font=("MS Gothic", 12, "bold")
        )
        self.status_label.pack(side="left", padx=15)

        # コンパクトクリック透過チェックボックス（ビュータブへ移動）
        tk.Checkbutton(
            top_frame,
            text="クリック透過",
            variable=self.click_through_var,
            command=self.toggle_click_through,
            bg="#0D1117",
            fg="white",
            selectcolor="#0D1117",
            font=("Meiryo", 10)
        ).pack(side="right", padx=10)

        # compactリンク
        link = tk.Label(
            top_frame,
            text="コンパクトモードで表示",
            fg="#4EA3FF",
            bg="#0D1117",
            cursor="hand2",
            font=("Meiryo", 10, "underline")
        )
        link.pack(side="right", padx=10)
        link.bind("<Button-1>", lambda e: self.toggle_mode_link())

        # ログクリア
        tk.Button(
            top_frame,
            text="ログクリア",
            command=self.clear_messages,
            bg="#1F2A44",
            fg="white",
            font=("Meiryo", 9)
        ).pack(side="right", padx=10)

        separator = tk.Frame(main_frame, height=2, bg="#3A6EA5")
        separator.pack(fill="x", pady=5)

        # フィルタ
        filter_frame = tk.Frame(main_frame, bg="#0D1117")
        filter_frame.pack(fill="x")

        for chat_type in chat_order:
            display_color = self.chat_display_colors.get(chat_type, "white")
            cb = tk.Checkbutton(
                filter_frame,
                text=chat_type,
                variable=self.filters[chat_type],
                command=lambda ct=chat_type: self.on_filter_changed(ct),
                bg="#0D1117",
                fg=display_color,
                selectcolor="#0D1117",
                font=("Meiryo", 10)
            )
            cb.pack(side="left", padx=5)

        # 検索バー
        search_frame = tk.Frame(main_frame, bg="#0D1117")
        search_frame.pack(fill="x", pady=0, padx=5)

        tk.Label(search_frame, text="検索:", bg="#0D1117", fg="white").pack(side="left")

        self.search_entry = tk.Entry(
            search_frame, width=16,
            bg="#000000", fg="white", insertbackground="white"
        )
        self.search_entry.pack(side="left", pady=0, padx=5)

        tk.Button(
            search_frame, text="◀前へ",
            command=self.search_prev,
            bg="#1F2A44", fg="white",
            height=1,
            pady=0,
            borderwidth=1,
            highlightthickness=1,
            font=("Meiryo", 7)
        ).pack(side="left", pady=3, padx=1)

        tk.Button(
            search_frame, text="次へ▶",
            command=self.search_next,
            bg="#1F2A44", fg="white",
            height=1,
            pady=0,
            borderwidth=1,
            highlightthickness=1,
            font=("Meiryo", 7)
        ).pack(side="left", pady=3, padx=1)

        # メインテキスト
        self.text_area = scrolledtext.ScrolledText(
            main_frame, width=80, height=35,
            bg="#000000", fg="white",
            insertbackground="white",
            font=("MS Gothic", 10)
        )
        self.text_area.pack(fill="both", expand=True)

        for ctype in chat_order:
            color = self.chat_display_colors.get(ctype, "white")
            self.text_area.tag_config(ctype, foreground=color)

        self.text_area.tag_config("search_highlight", background="#FFD56B", foreground="black")
        self.search_index = "1.0"

    # ============================================================
    #   設定タブ（スクロール対応）
    # ============================================================
    def build_settings_tab(self):

        canvas = tk.Canvas(self.tab_settings, bg="#0D1117", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.tab_settings, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frame = tk.Frame(canvas, bg="#0D1117")
        canvas.create_window((0, 0), window=frame, anchor="nw")

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        frame.bind("<Configure>", on_configure)

        # マウスホイールでスクロール可能にする
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # タイトル
        title = tk.Label(frame, text="設定", font=("Meiryo", 14, "bold"),
                         bg="#0D1117", fg="white")
        title.pack(pady=10)

        # 設定を維持
        keep_frame = tk.Frame(frame, bg="#0D1117")
        keep_frame.pack(fill="x", padx=10, pady=(0, 10))

        tk.Checkbutton(
            keep_frame,
            text="設定を維持",
            variable=self.remember_state,
            command=self.save_current_settings,
            bg="#0D1117",
            fg="white",
            selectcolor="#0D1117",
            font=("Meiryo", 10)
        ).pack(anchor="w")

        # フォルダ設定
        folder_frame = tk.LabelFrame(frame, text="フォルダ設定",
                                     bg="#0D1117", fg="white")
        folder_frame.pack(fill="x", padx=10, pady=10)

        tk.Button(
            folder_frame, text="フォルダ選択", command=self.select_folder,
            bg="#1F2A44", fg="white"
        ).pack(side="left", padx=5, pady=5)

        self.folder_label = tk.Label(
            folder_frame,
            text=self.base_folder,
            bg="#0D1117", fg="white"
        )
        self.folder_label.pack(side="left", padx=10)

        # 表示切替
        option_frame = tk.LabelFrame(frame, text="表示切替 ※GUIのみ",
                                     bg="#0D1117", fg="white")
        option_frame.pack(fill="x", padx=10, pady=10)

        tk.Checkbutton(
            option_frame,
            text="時刻を表示( [ x時 xx分 xx秒] )",
            variable=self.show_time,
            command=lambda: self.on_filter_changed(None),
            bg="#0D1117",
            fg="white",
            selectcolor="#0D1117",
            font=("Meiryo", 10)
        ).pack(side="left", padx=5)

        tk.Checkbutton(
            option_frame,
            text="メッセージ種類を表示( [クラブ]など )",
            variable=self.show_label,
            command=lambda: self.on_filter_changed(None),
            bg="#0D1117",
            fg="white",
            selectcolor="#0D1117",
            font=("Meiryo", 10)
        ).pack(side="left", padx=5)

        # 色設定
        frame_colors = tk.LabelFrame(frame, text="チャット色設定",
                                     bg="#0D1117", fg="white")
        frame_colors.pack(fill="x", padx=10, pady=10)

        for ctype in chat_order:
            row = tk.Frame(frame_colors, bg="#0D1117")
            row.pack(fill="x", pady=3)

            lbl = tk.Label(row, text=ctype, width=10,
                           bg="#0D1117", fg="white")
            lbl.pack(side="left")

            preview = tk.Label(
                row,
                text="      ",
                bg=self.chat_display_colors.get(ctype, "white"),
                fg=self.chat_display_colors.get(ctype, "white"),
                width=8,
                height=1
            )
            preview.pack(side="left", padx=5)

            def make_cmd(ct=ctype, pv=preview):
                def _cmd():
                    color = colorchooser.askcolor(
                        color=self.chat_display_colors.get(ct, "white"),
                        title=f"{ct} の色を選択"
                    )[1]
                    if color:
                        self.chat_display_colors[ct] = color
                        pv.config(bg=color, fg=color)
                        self.text_area.tag_config(ct, foreground=color)
                        if hasattr(self, "compact_text") and self.compact_text.winfo_exists():
                            self.compact_text.tag_config(ct, foreground=color)
                        self.save_current_settings()
                return _cmd

            tk.Button(
                row, text="色を選ぶ", command=make_cmd(),
                bg="#1F2A44", fg="white"
            ).pack(side="left", padx=5)

        # 除外ログ
        frame_exclude = tk.LabelFrame(frame, text="除外ログ設定 ※チェックONで表示、OFFで非表示",
                                      bg="#0D1117", fg="white")
        frame_exclude.pack(fill="x", padx=10, pady=10)

        for pat in EXCLUDE_PATTERNS:
            label = EXCLUDE_LABELS.get(pat, pat)
            tk.Checkbutton(
                frame_exclude,
                text=label,
                variable=self.exclude_options[pat],
                command=self.save_current_settings,
                bg="#0D1117",
                fg="white",
                selectcolor="#0D1117",
                font=("Meiryo", 10)
            ).pack(anchor="w", pady=2)

        # NG / SP ワード設定（横並び）
        frame_ngsp = tk.LabelFrame(frame, text="NG / SP ワード設定",
                                   bg="#0D1117", fg="white")
        frame_ngsp.pack(fill="x", padx=10, pady=10)

        container = tk.Frame(frame_ngsp, bg="#0D1117")
        container.pack(fill="x")

        # --- NGワード ---
        ng_frame = tk.Frame(container, bg="#0D1117")
        ng_frame.pack(side="left", fill="both", expand=True, padx=5)

        tk.Label(ng_frame, text="NGワード:", bg="#0D1117", fg="white").pack(anchor="w")

        self.ng_entry = tk.Entry(ng_frame, bg="#0D1117", fg="white", insertbackground="white")
        self.ng_entry.pack(fill="x", padx=5, pady=2)

        tk.Button(ng_frame, text="追加", command=self.add_ng_word,
                  bg="#1F2A44", fg="white").pack(side="left", anchor="n", padx=3)
        tk.Button(ng_frame, text="削除", command=self.remove_ng_word,
                  bg="#1F2A44", fg="white").pack(side="left", anchor="n", padx=3)

        self.ng_listbox = Listbox(ng_frame, height=6, bg="#0D1117", fg="white")
        self.ng_listbox.pack(fill="both", expand=True, pady=5)

        # --- SPワード ---
        sp_frame = tk.Frame(container, bg="#0D1117")
        sp_frame.pack(side="left", fill="both", expand=True, padx=5)

        tk.Label(sp_frame, text="SPワード:", bg="#0D1117", fg="white").pack(anchor="w")

        self.sp_entry = tk.Entry(sp_frame, bg="#0D1117", fg="white", insertbackground="white")
        self.sp_entry.pack(fill="x", padx=5, pady=2)

        tk.Button(sp_frame, text="追加", command=self.add_sp_word,
                  bg="#1F2A44", fg="white").pack(side="left", anchor="n", padx=3)
        tk.Button(sp_frame, text="削除", command=self.remove_sp_word,
                  bg="#1F2A44", fg="white").pack(side="left", anchor="n", padx=3)

        self.sp_listbox = Listbox(sp_frame, height=6, bg="#0D1117", fg="white")
        self.sp_listbox.pack(fill="both", expand=True, pady=5)

    # ============================================================
    #   NG / SP
    # ============================================================
    def add_ng_word(self):
        word = self.ng_entry.get().strip()
        if word and word not in self.ng_words:
            self.ng_words.append(word)
            self.ng_listbox.insert(tk.END, word)
            self.ng_entry.delete(0, tk.END)
            self.save_current_settings()
            self.redraw_messages()
            self.update_compact_messages()

    # ============================================================
    #   NG / SP
    # ============================================================

    def remove_ng_word(self):
        selection = self.ng_listbox.curselection()
        if selection:
            index = selection[0]
            word = self.ng_listbox.get(index)
            self.ng_words.remove(word)
            self.ng_listbox.delete(index)
            self.save_current_settings()
            self.redraw_messages()
            self.update_compact_messages()

    # ============================================================
    #   NG / SP ワード処理（続き）
    # ============================================================
    def remove_sp_word(self):
        selection = self.sp_listbox.curselection()
        if selection:
            index = selection[0]
            word = self.sp_listbox.get(index)
            self.sp_words.remove(word)
            self.sp_listbox.delete(index)
            self.save_current_settings()
            self.redraw_messages()
            self.update_compact_messages()

    # ============================================================
    #   NG / SP ワード処理（続き）
    # ============================================================
    def add_sp_word(self):
        word = self.sp_entry.get().strip()
        if word and word not in self.sp_words:
            self.sp_words.append(word)
            self.sp_listbox.insert(tk.END, word)
            self.sp_entry.delete(0, tk.END)
            self.save_current_settings()
            self.redraw_messages()
            self.update_compact_messages()

    # ============================================================
    #   フィルタ変更
    # ============================================================
    def on_filter_changed(self, chat_type):
        self.redraw_messages()
        self.update_compact_messages()
        self.refresh_compact_tabs()

    def refresh_compact_tabs(self):
        if not hasattr(self, "compact_tabs"):
            return

        for chat_type, frame in self.compact_tabs.items():
            state = self.filters[chat_type].get()
            frame.config(bg="white" if state else "black")

            for child in frame.winfo_children():
                child.config(
                    bg=frame["bg"],
                    fg="black" if state else "white"
                )

    # ============================================================
    #   差分描画：メインテキスト
    # ============================================================
    def append_to_main_text(self, chat_type, timestamp, message, scroll=True):
        is_sp = any(sp in message for sp in self.sp_words)
        is_ng = any(ng in message for ng in self.ng_words)

        if is_ng and not is_sp:
            return

        if not is_sp and not self.filters[chat_type].get():
            return

        line = ""
        if self.show_time.get():
            line += f"{timestamp} "
        if self.show_label.get():
            line += f"[{chat_type}] "
        line += f"{message}\n"

        self.text_area.insert(tk.END, line, chat_type)
        if scroll:
            self.text_area.see(tk.END)

    # ============================================================
    #   差分描画：コンパクトテキスト
    # ============================================================
    def append_to_compact(self, chat_type, message, scroll=True):
        if not hasattr(self, "compact_text") or not self.compact_text.winfo_exists():
            return

        is_sp = any(sp in message for sp in self.sp_words)
        is_ng = any(ng in message for ng in self.ng_words)

        if is_ng and not is_sp:
            return

        if not is_sp and not self.filters[chat_type].get():
            return

        line = f"{message}\n"

        self.compact_text.config(state="normal")
        self.compact_text.insert(tk.END, line, chat_type)
        if scroll:
            self.compact_text.see(tk.END)
        self.compact_text.config(state="disabled")

    # ============================================================
    #   メッセージ追加
    # ============================================================
    def add_message(self, chat_type, timestamp, message):
        self.messages.append((chat_type, timestamp, message))

        if len(self.messages) > 5000:
            del self.messages[:100]

        self.append_to_main_text(chat_type, timestamp, message)

        if hasattr(self, "compact_text") and self.compact_text.winfo_exists():
            self.append_to_compact(chat_type, message)

    # ============================================================
    #   再描画・クリア
    # ============================================================
    def redraw_messages(self):
        self.text_area.delete("1.0", tk.END)

        for chat_type, timestamp, message in self.messages:
            self.append_to_main_text(chat_type, timestamp, message, scroll=False)

        self.text_area.see(tk.END)

    def clear_messages(self):
        self.messages.clear()
        self.redraw_messages()
        self.update_compact_messages()

    # ============================================================
    #   検索機能
    # ============================================================
    def clear_search_highlight(self):
        self.text_area.tag_remove("search_highlight", "1.0", tk.END)

    def search_next(self):
        pattern = self.search_entry.get().strip()
        if not pattern:
            return
        self.clear_search_highlight()
        idx = self.text_area.search(pattern, self.search_index, nocase=True, stopindex=tk.END)
        if not idx:
            self.search_index = "1.0"
            return
        end_idx = f"{idx}+{len(pattern)}c"
        self.text_area.tag_add("search_highlight", idx, end_idx)
        self.text_area.see(idx)
        self.search_index = end_idx

    def search_prev(self):
        pattern = self.search_entry.get().strip()
        if not pattern:
            return
        self.clear_search_highlight()
        idx = self.text_area.search(pattern, self.search_index, nocase=True, stopindex="1.0", backwards=True)
        if not idx:
            self.search_index = tk.END
            return
        end_idx = f"{idx}+{len(pattern)}c"
        self.text_area.tag_add("search_highlight", idx, end_idx)
        self.text_area.see(idx)
        self.search_index = idx

    # ============================================================
    #   フォルダ選択
    # ============================================================
    def select_folder(self):
        folder = filedialog.askdirectory(initialdir=self.base_folder)
        if folder:
            self.base_folder = folder
            self.folder_label.config(text=self.base_folder)
            self.save_current_settings()

    # ============================================================
    #   設定保存
    # ============================================================
    def save_current_settings(self):
        data = {
            "folder": self.base_folder,
            "chat_display_colors": self.chat_display_colors,
            "exclude_options": {pat: var.get() for pat, var in self.exclude_options.items()},
            "filters": {ctype: var.get() for ctype, var in self.filters.items()},
            "ng_words": self.ng_words,
            "sp_words": self.sp_words,
            "show_time": self.show_time.get(),
            "show_label": self.show_label.get(),
            "remember_state": self.remember_state.get(),
        }
        save_settings(data)

    # ============================================================
    #   監視開始 / 停止
    # ============================================================
    def start_monitor(self):
        if self.monitoring:
            return
        self.monitoring = True
        self.status_label.config(text="監視中", fg="#4CAF50")

        today = time.strftime("%Y_%m_%d")
        filename = os.path.join(self.base_folder, f"TWChatLog_{today}.html")

        t = threading.Thread(target=poll_file, args=(filename, self), daemon=True)
        t.start()

    def stop_monitor(self):
        self.monitoring = False
        self.status_label.config(text="停止中", fg="#3A6EA5")

    # ============================================================
    #   クリック透過（compact）
    # ============================================================
    def toggle_click_through(self):
        if not hasattr(self, "compact_window") or not self.compact_window.winfo_exists():
            return

        hwnd = windll.user32.GetParent(self.compact_window.winfo_id())
        ex_style = windll.user32.GetWindowLongW(hwnd, -20)

        WS_EX_TRANSPARENT = 0x20
        WS_EX_LAYERED = 0x80000

        enable = self.click_through_var.get()

        if enable:
            new_style = ex_style | WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            new_style = ex_style & ~WS_EX_TRANSPARENT

        windll.user32.SetWindowLongW(hwnd, -20, new_style)

    # ============================================================
    #   compact：フル再描画
    # ============================================================
    def update_compact_messages(self):
        if not hasattr(self, "compact_text") or not self.compact_text.winfo_exists():
            return

        self.compact_text.config(state="normal")
        self.compact_text.delete("1.0", tk.END)

        for chat_type, timestamp, message in self.messages:
            self.append_to_compact(chat_type, message, scroll=False)

        self.compact_text.see(tk.END)
        self.compact_text.config(state="disabled")

    # ============================================================
    #   コンパクトモード：リンククリック
    # ============================================================
    def toggle_mode_link(self):
        self.compact_mode.set(True)
        self.toggle_mode()

    # ============================================================
    #   コンパクトモード ON/OFF
    # ============================================================
    def toggle_mode(self):
        if self.compact_mode.get():
            self.open_compact_window()
        else:
            if hasattr(self, "compact_window") and self.compact_window.winfo_exists():
                self.compact_window.destroy()

    # ============================================================
    #   コンパクトウィンドウ生成
    # ============================================================
    def open_compact_window(self):
    # すでに compact_window が存在する場合は閉じる
        if (
            hasattr(self, "compact_window")
            and self.compact_window is not None
            and self.compact_window.winfo_exists()
        ):
            self.compact_window.destroy()
        self.compact_window = tk.Toplevel()
        self.compact_window.title("コンパクトチャット")
        self.compact_window.configure(bg="black")

        self.compact_window.geometry("390x200+1280+880")
        self.compact_window.attributes("-topmost", True)
        self.compact_window.attributes("-alpha", 0.85)
        self.compact_window.overrideredirect(True)
        self.compact_window.resizable(True, True)

        # --- 上端リサイズバー ---
        resize_bar = tk.Frame(
            self.compact_window,
            height=5,
            bg="black",
            cursor="sb_v_double_arrow",
            highlightbackground="white",
            highlightthickness=0.5
        )
        resize_bar.pack(fill="x", padx=0, pady=0)
        resize_bar.bind("<Button-1>", self.start_resize)
        resize_bar.bind("<B1-Motion>", self.do_resize)

        # --- タイトルバー ---
        title_bar = tk.Frame(
            self.compact_window,
            height=2,
            bg="black",
            highlightbackground="white",
            highlightthickness=0.5
        )
        title_bar.pack(fill="x", padx=0, pady=0)

        drag_area = tk.Frame(title_bar, bg="black", height=10)
        drag_area.pack(side="left", fill="x", expand=True)
        drag_area.bind("<Button-1>", self.start_move)
        drag_area.bind("<B1-Motion>", self.do_move)

        # --- タブ ---
        tab_frame = tk.Frame(self.compact_window, bg="black")
        tab_frame.pack(fill="x", pady=0)

        self.compact_tabs = {}
        tab_list = ["一般", "耳打ち", "チーム", "クラブ", "システム", "叫ぶ"]

        for chat_type in tab_list:
            frame = tk.Frame(
                tab_frame,
                bg="white" if self.filters[chat_type].get() else "black",
                highlightbackground="black",
                highlightthickness=0.5,
                padx=10, pady=0
            )
            frame.pack(side="left", padx=0)

            label = tk.Label(
                frame,
                text=chat_type,
                bg=frame["bg"],
                fg="black" if frame["bg"] == "white" else "white",
                font=("Meiryo", 7),
                pady=0, padx=0
            )
            label.pack()

            frame.bind("<Button-1>", lambda e, ct=chat_type: self.toggle_compact_tab(ct))
            label.bind("<Button-1>", lambda e, ct=chat_type: self.toggle_compact_tab(ct))

            self.compact_tabs[chat_type] = frame

        # --- 閉じるボタン ---
        clear_tab_frame = tk.Frame(
            tab_frame,
            bg="black",
            highlightbackground="white",
            highlightthickness=0.5,
            padx=0, pady=0
        )
        clear_tab_frame.pack(side="right", padx=0, pady=0)

        tk.Button(
            clear_tab_frame,
            text="閉じる",
            command=self.restore_main_window,
            bg="black", fg="white",
            font=("Meiryo", 7),
            bd=0,
            padx=0, pady=0
        ).pack()

        # --- チャット欄 ---
        text_frame = tk.Frame(
            self.compact_window,
            bg="black",
            highlightbackground="white",
            highlightthickness=1
        )
        text_frame.pack(fill="both", expand=True, padx=0, pady=0)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        self.compact_text = tk.Text(
            text_frame,
            bg="black", fg="white",
            font=("MS Gothic", 9),
            yscrollcommand=scrollbar.set,
            wrap="char",
            bd=0,
            padx=0, pady=0,
            highlightthickness=0
        )
        self.compact_text.pack(fill="both", expand=True)
        scrollbar.config(command=self.compact_text.yview)

        # 色タグ
        for ctype in chat_order:
            color = self.chat_display_colors.get(ctype, "white")
            self.compact_text.tag_config(ctype, foreground=color)

        self.update_compact_messages()
        self.toggle_click_through()

    # ============================================================
    #   compact：ドラッグ移動
    # ============================================================
    def start_move(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def do_move(self, event):
        x = self.compact_window.winfo_x() + event.x - self._drag_x
        y = self.compact_window.winfo_y() + event.y - self._drag_y
        self.compact_window.geometry(f"+{x}+{y}")

    # ============================================================
    #   compact：リサイズ
    # ============================================================
    def start_resize(self, event):
        self._resize_start_y = event.y_root
        self._start_height = self.compact_window.winfo_height()
        self._start_y = self.compact_window.winfo_y()

    def do_resize(self, event):
        dy = event.y_root - self._resize_start_y
        new_height = self._start_height - dy
        new_y = self._start_y + dy

        if new_height < 180:
            return

        self.compact_window.geometry(
            f"{self.compact_window.winfo_width()}x{new_height}+{self.compact_window.winfo_x()}+{new_y}"
        )

    # ============================================================
    #   compact：閉じる
    # ============================================================
    def restore_main_window(self):
        self.compact_mode.set(False)
        self.toggle_mode()

    # ============================================================
    #   compact：タブ切り替え
    # ============================================================
    def toggle_compact_tab(self, chat_type):
        current = self.filters[chat_type].get()
        new_state = not current
        self.filters[chat_type].set(new_state)

        frame = self.compact_tabs[chat_type]
        frame.config(bg="white" if new_state else "black")

        for child in frame.winfo_children():
            child.config(
                bg=frame["bg"],
                fg="black" if new_state else "white"
            )

        self.update_compact_messages()
        self.redraw_messages()


# ============================================================
#   ファイル監視
# ============================================================
def poll_file(filename, viewer):
    last_size = 0
    current_file = filename

    while viewer.monitoring:
        try:
            today = time.strftime("%Y_%m_%d")
            expected_file = os.path.join(viewer.base_folder, f"TWChatLog_{today}.html")

            if expected_file != current_file:
                current_file = expected_file
                last_size = 0

            if not os.path.exists(current_file):
                time.sleep(1)
                continue

            size = os.path.getsize(current_file)
            if size > last_size:
                with open(current_file, encoding="cp932", errors="ignore") as f:
                    f.seek(last_size)
                    new_data = f.read()
                    last_size = size

                soup = BeautifulSoup(new_data, "html.parser")
                fonts = soup.find_all("font")

                for i in range(0, len(fonts)-1, 2):
                    time_font = fonts[i]
                    chat_font = fonts[i+1]

                    timestamp = time_font.text.strip()
                    color = chat_font.get("color", "").lower()
                    text = chat_font.text.strip()

                    skip = False
                    for pat in EXCLUDE_PATTERNS:
                        if text.startswith(pat) and not viewer.exclude_options[pat].get():
                            skip = True
                            break
                    if skip:
                        continue

                    if color in chat_colors:
                        chat_type, _ = chat_colors[color]

                        is_sp = any(sp in text for sp in viewer.sp_words)
                        is_ng = any(ng in text for ng in viewer.ng_words)

                        if is_ng and not is_sp:
                            continue

                        viewer.add_message(chat_type, timestamp, text)

        except Exception as e:
            print("エラー:", e)

        time.sleep(1)


# ============================================================
#   main
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    viewer = ChatViewerVer3(root)
    root.mainloop()