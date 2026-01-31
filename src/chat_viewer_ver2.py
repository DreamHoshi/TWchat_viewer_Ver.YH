import time
import os
import sys
import json
import tkinter as tk
from tkinter import scrolledtext, Listbox, filedialog
from bs4 import BeautifulSoup
import threading
from collections import OrderedDict
from PIL import Image, ImageTk
import ctypes
from ctypes import windll

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
#   チャット色設定
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

# ============================================================
#   メインクラス
# ============================================================
class ChatViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("チャットログビューア")
        self.root.iconbitmap(resource_path("zelippi_icon.ico"))

        # JSON 読み込み
        self.settings = load_settings()

        # メインフレーム
        main_frame = tk.Frame(self.root, bg="#0D1117")
        main_frame.pack(fill="both", expand=True)

        # --------------------------------------------------------
        # フォルダ選択
        # --------------------------------------------------------
        folder_frame = tk.Frame(main_frame, bg="#0D1117")
        folder_frame.pack(fill="x", pady=5)

        tk.Button(folder_frame, text="フォルダ選択", command=self.select_folder,
                  bg="#1F2A44", fg="white").pack(side="left", padx=5)

        self.base_folder = self.settings.get("folder", "C:\\Nexon\\TalesWeaver\\ChatLog")

        self.folder_label = tk.Label(
            folder_frame,
            text=self.base_folder,
            bg="#0D1117", fg="white"
        )
        self.folder_label.pack(side="left", padx=10)

        tk.Button(folder_frame, text="読み込み開始", command=self.start_monitor,
                  bg="#1F2A44", fg="white").pack(side="left", padx=5)

        tk.Button(folder_frame, text="停止", command=self.stop_monitor,
                  bg="#1F2A44", fg="white").pack(side="left", padx=5)

        self.status_label = tk.Label(
            folder_frame,
            text="停止中",
            bg="#0D1117",
            fg="#3A6EA5",
            font=("MS Gothic", 12, "bold")
        )
        self.status_label.pack(side="left", padx=15)

        # --------------------------------------------------------
        # フィルタ
        # --------------------------------------------------------
        filter_frame = tk.Frame(main_frame, bg="#0D1117")
        filter_frame.pack(fill="x")

        self.filters = {}
        saved_filters = self.settings.get("filters", {})

        for chat_type in chat_order:
            var = tk.BooleanVar(value=saved_filters.get(chat_type, True))

            # チャット種別の文字色
            display_color = "white"
            for c, (ctype, disp) in chat_colors.items():
                if ctype == chat_type:
                    display_color = disp
                    break

            # ★ 同期対応：command を on_filter_changed に変更
            cb = tk.Checkbutton(
                filter_frame,
                text=chat_type,
                variable=var,
                command=lambda ct=chat_type: self.on_filter_changed(ct),
                bg="#0D1117",
                fg=display_color,
                selectcolor="#0D1117",
                font=("Meiryo", 10)
            )
            cb.pack(side="left", padx=5)
            self.filters[chat_type] = var

        # ログクリア
        tk.Button(
            filter_frame,
            text="ログクリア",
            command=self.clear_messages,
            bg="#1F2A44",
            fg="white",
            font=("Meiryo", 9)
        ).pack(side="right", padx=10)

        separator = tk.Frame(main_frame, height=2, bg="#3A6EA5")
        separator.pack(fill="x", pady=5)

        # --------------------------------------------------------
        # 表示切替
        # --------------------------------------------------------
        option_frame = tk.Frame(main_frame, bg="#0D1117")
        option_frame.pack(fill="x")

        self.show_time = tk.BooleanVar(value=self.settings.get("show_time", True))
        self.show_label = tk.BooleanVar(value=self.settings.get("show_label", True))
        self.remember_state = tk.BooleanVar(value=self.settings.get("remember_state", False))

        tk.Checkbutton(
            option_frame,
            text="時刻を表示",
            variable=self.show_time,
            command=lambda: self.on_filter_changed(None),
            bg="#0D1117",
            fg="white",
            selectcolor="#0D1117",
            font=("Meiryo", 10)
        ).pack(side="left", padx=5)

        tk.Checkbutton(
            option_frame,
            text="メッセージ種類を表示",
            variable=self.show_label,
            command=lambda: self.on_filter_changed(None),
            bg="#0D1117",
            fg="white",
            selectcolor="#0D1117",
            font=("Meiryo", 10)
        ).pack(side="left", padx=5)
        # 設定を維持
        tk.Checkbutton(
            option_frame,
            text="設定を維持",
            variable=self.remember_state,
            command=self.save_current_settings,
            bg="#0D1117",
            fg="white",
            selectcolor="#0D1117",
            font=("Meiryo", 10)
        ).pack(side="right", padx=10)

        self.click_through_var = tk.BooleanVar(value=False)
        self.click_cb = tk.Checkbutton(
            option_frame,
            text="クリックを透過",
            variable=self.click_through_var,
            command=self.toggle_click_through,
            bg="#0D1117",
            fg="white",
            selectcolor="#0D1117",
            font=("Meiryo", 10)
        )
        self.click_cb.pack(side="right", padx=5)

        # --------------------------------------------------------
        # コンパクトモード（リンク風）
        # --------------------------------------------------------
        self.compact_mode = tk.BooleanVar(value=False)

        link = tk.Label(
            option_frame,
            text="コンパクトモードで表示",
            fg="#4EA3FF",
            bg="#0D1117",
            cursor="hand2",
            font=("Meiryo", 10, "underline")
        )
        link.pack(side="right", padx=10)
        link.bind("<Button-1>", lambda e: self.toggle_mode_link())

        # --------------------------------------------------------
        # NG / SP / 検索
        # --------------------------------------------------------
        toggle_frame = tk.Frame(main_frame, bg="#0D1117")
        toggle_frame.pack(fill="x")

        self.toggle_button = tk.Button(
            toggle_frame, text="NG ▼", width=6,
            command=self.toggle_ng_frame,
            bg="#1F2A44", fg="white"
        )
        self.toggle_button.pack(side="left", padx=5)

        self.toggle_button2 = tk.Button(
            toggle_frame, text="SP ▼", width=6,
            command=self.toggle_sp_frame,
            bg="#1F2A44", fg="white"
        )
        self.toggle_button2.pack(side="left", padx=5)

        # 検索バー
        search_frame = tk.Frame(toggle_frame, bg="#0D1117")
        search_frame.pack(side="right", padx=5)

        tk.Label(search_frame, text="検索:", bg="#0D1117", fg="white").pack(side="left")

        self.search_entry = tk.Entry(
            search_frame, width=20,
            bg="#000000", fg="white", insertbackground="white"
        )
        self.search_entry.pack(side="left", padx=3)

        tk.Button(
            search_frame, text="次へ",
            command=self.search_next,
            bg="#3A6EA5", fg="white"
        ).pack(side="left", padx=2)

        tk.Button(
            search_frame, text="前へ",
            command=self.search_prev,
            bg="#3A6EA5", fg="white"
        ).pack(side="left", padx=2)

        # --------------------------------------------------------
        # NGワード
        # --------------------------------------------------------
        self.ng_frame = tk.Frame(toggle_frame, relief="groove", borderwidth=2, bg="#1F2A44")
        ng_top = tk.Frame(self.ng_frame, bg="#1F2A44")
        ng_top.pack(fill="x")

        tk.Label(ng_top, text="NGワード:", bg="#1F2A44", fg="white").pack(side="left")

        self.ng_entry = tk.Entry(ng_top, bg="#0D1117", fg="white", insertbackground="white")
        self.ng_entry.pack(side="left", fill="x", expand=True)

        tk.Button(
            ng_top, text="追加",
            command=self.add_ng_word,
            bg="#3A6EA5", fg="white"
        ).pack(side="left")

        tk.Button(
            ng_top, text="削除",
            command=self.remove_ng_word,
            bg="#3A6EA5", fg="white"
        ).pack(side="left")

        self.ng_listbox = Listbox(self.ng_frame, height=4, bg="#0D1117", fg="white")
        self.ng_listbox.pack(fill="x", pady=5)

        # --------------------------------------------------------
        # SPワード
        # --------------------------------------------------------
        self.sp_frame = tk.Frame(toggle_frame, relief="groove", borderwidth=2, bg="#1F2A44")
        sp_top = tk.Frame(self.sp_frame, bg="#1F2A44")
        sp_top.pack(fill="x")

        tk.Label(sp_top, text="特別ワード:", bg="#1F2A44", fg="white").pack(side="left")

        self.sp_entry = tk.Entry(sp_top, bg="#0D1117", fg="white", insertbackground="white")
        self.sp_entry.pack(side="left", fill="x", expand=True)

        tk.Button(
            sp_top, text="追加",
            command=self.add_sp_word,
            bg="#3A6EA5", fg="white"
        ).pack(side="left")

        tk.Button(
            sp_top, text="削除",
            command=self.remove_sp_word,
            bg="#3A6EA5", fg="white"
        ).pack(side="left")

        self.sp_listbox = Listbox(self.sp_frame, height=4, bg="#0D1117", fg="white")
        self.sp_listbox.pack(fill="x", pady=5)

        # --------------------------------------------------------
        # チャット表示エリア
        # --------------------------------------------------------
        self.text_area = scrolledtext.ScrolledText(
            main_frame, width=80, height=30,
            bg="#000000", fg="white",
            insertbackground="white",
            font=("MS Gothic", 10)
        )
        self.text_area.pack(fill="both", expand=True)

        for chat_type, color in set(chat_colors.values()):
            self.text_area.tag_config(chat_type, foreground=color)

        self.text_area.tag_config("search_highlight", background="#FFD56B", foreground="black")
        self.search_index = "1.0"

        # NG/SP 初期化
        self.ng_words = self.settings.get("ng_words", [])
        self.sp_words = self.settings.get("sp_words", [])

        for w in self.ng_words:
            self.ng_listbox.insert(tk.END, w)

        for w in self.sp_words:
            self.sp_listbox.insert(tk.END, w)

        # メッセージ保持
        self.messages = []

        # 初期状態では非表示
        self.ng_frame.pack_forget()
        self.sp_frame.pack_forget()

        # 監視フラグ
        self.monitoring = False

        # 設定復元
        if self.remember_state.get():
            saved_filters = self.settings.get("filters", {})
            for chat_type in chat_order:
                if chat_type in saved_filters:
                    self.filters[chat_type].set(saved_filters[chat_type])

            self.folder_label.config(text=self.base_folder)
    # ============================================================
    #   検索
    # ============================================================
    def search_next(self):
        word = self.search_entry.get()
        if not word:
            return

        self.text_area.tag_remove("search_highlight", "1.0", tk.END)

        pos = self.text_area.search(word, self.search_index, tk.END)
        if not pos:
            self.search_index = "1.0"
            return

        end_pos = f"{pos}+{len(word)}c"
        self.text_area.tag_add("search_highlight", pos, end_pos)
        self.text_area.see(pos)
        self.search_index = end_pos

    def search_prev(self):
        word = self.search_entry.get()
        if not word:
            return

        self.text_area.tag_remove("search_highlight", "1.0", tk.END)

        pos = self.text_area.search(word, self.search_index, backwards=True)
        if not pos:
            self.search_index = tk.END
            return

        end_pos = f"{pos}+{len(word)}c"
        self.text_area.tag_add("search_highlight", pos, end_pos)
        self.text_area.see(pos)
        self.search_index = pos

    # ============================================================
    #   NGワード追加
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
    #   NGワード削除
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
    #   SPワード追加
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
    #   SPワード削除
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
    #   ★ チェックボックス変更時の同期処理（追加）
    # ============================================================
    def on_filter_changed(self, chat_type):
        self.redraw_messages()
        self.update_compact_messages()
        self.refresh_compact_tabs()

    # ============================================================
    #   ★ コンパクトタブの色を同期（追加）
    # ============================================================
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
    #   差分描画：メインテキストに 1 行追加
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
    #   差分描画：コンパクトテキストに 1 行追加
    # ============================================================
    def append_to_compact(self, chat_type, message, scroll=True):
        # compact_text が存在しない場合は何もしない
        if not hasattr(self, "compact_text") or not self.compact_text.winfo_exists():
            return

        # NG / SP 判定
        is_sp = any(sp in message for sp in self.sp_words)
        is_ng = any(ng in message for ng in self.ng_words)

        if is_ng and not is_sp:
            return

        if not is_sp and not self.filters[chat_type].get():
            return
        
        line = f"{message}\n"

        # compact_text に追加
        self.compact_text.config(state="normal")
        self.compact_text.insert(tk.END, line, chat_type)
        if scroll:
            self.compact_text.see(tk.END)
        self.compact_text.config(state="disabled")

    # ============================================================
    #   メッセージ追加（差分描画版）
    # ============================================================
    def add_message(self, chat_type, timestamp, message):
        self.messages.append((chat_type, timestamp, message))

        # 5000行を超えたら100行だけ削除（Text側は削除しない）
        if len(self.messages) > 5000:
            del self.messages[:100]

        # 差分描画
        self.append_to_main_text(chat_type, timestamp, message)

        if hasattr(self, "compact_text") and self.compact_text.winfo_exists():
            self.append_to_compact(chat_type, message)

    # ============================================================
    #   メインテキスト：フル再描画
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
    #   NGフレームの開閉
    # ============================================================
    def toggle_ng_frame(self):
        if self.ng_frame.winfo_ismapped():
            self.ng_frame.pack_forget()
            self.toggle_button.config(text="NG ▼")
        else:
            self.ng_frame.pack(fill="x", pady=5)
            self.toggle_button.config(text="NG ▲")

    # ============================================================
    #   SPフレームの開閉
    # ============================================================
    def toggle_sp_frame(self):
        if self.sp_frame.winfo_ismapped():
            self.sp_frame.pack_forget()
            self.toggle_button2.config(text="SP ▼")
        else:
            self.sp_frame.pack(fill="x", pady=5)
            self.toggle_button2.config(text="SP ▲")

    # ============================================================
    #   フォルダ選択
    # ============================================================
    def select_folder(self):
        folder = filedialog.askdirectory(title="チャットログフォルダを選択してください")
        if folder:
            self.base_folder = folder
            self.folder_label.config(text=self.base_folder)
            self.save_current_settings()

    # ============================================================
    #   設定保存
    # ============================================================
    def save_current_settings(self):
        if not self.remember_state.get():
            return

        data = {
            "show_time": self.show_time.get(),
            "show_label": self.show_label.get(),
            "remember_state": self.remember_state.get(),
            "folder": self.base_folder,
            "ng_words": self.ng_words,
            "sp_words": self.sp_words,
            "filters": {k: v.get() for k, v in self.filters.items()}
        }
        save_settings(data)

    # ============================================================
    #   監視開始
    # ============================================================
    def start_monitor(self):
        self.monitoring = True
        self.status_label.config(text="動作中", fg="#ff6464")
        self.save_current_settings()

        today = time.strftime("%Y_%m_%d")
        filename = os.path.join(self.base_folder, f"TWChatLog_{today}.html")

        t = threading.Thread(target=poll_file, args=(filename, self), daemon=True)
        t.start()

    # ============================================================
    #   停止
    # ============================================================
    def stop_monitor(self):
        self.monitoring = False
        self.status_label.config(text="停止中", fg="#3A6EA5")
        self.save_current_settings()

    # ============================================================
    #   クリック透過
    # ============================================================
    def toggle_click_through(self):
        if not hasattr(self, "compact_window") or not self.compact_window.winfo_exists():
            return

        hwnd = windll.user32.GetParent(self.compact_window.winfo_id())
        ex_style = windll.user32.GetWindowLongW(hwnd, -20)

        WS_EX_TRANSPARENT = 0x20
        WS_EX_LAYERED = 0x80000

        # チェックボックスの値をそのまま使う
        enable = self.click_through_var.get()

        if enable:
            # 透過 ON（クリックを通す）
            new_style = ex_style | WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            # 透過 OFF（クリックできる）
            new_style = ex_style & ~WS_EX_TRANSPARENT

        windll.user32.SetWindowLongW(hwnd, -20, new_style)

    # ============================================================
    #   コンパクトモード（リンククリック）
    # ============================================================
    def toggle_mode_link(self):
        self.compact_mode.set(True)
        self.toggle_mode()

    # ============================================================
    #   コンパクトモード切り替え
    # ============================================================
    def toggle_mode(self):
        if self.compact_mode.get():
            self.open_compact_window()
        else:
            if hasattr(self, "compact_window") and self.compact_window.winfo_exists():
                self.compact_window.destroy()

    # ============================================================
    #   コンパクトモードウィンドウ生成
    # ============================================================
    def open_compact_window(self):
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
            font=("MS Gothic", 10),
            yscrollcommand=scrollbar.set,
            wrap="char",
            bd=0,
            padx=0, pady=0,
            highlightthickness=0
        )
        self.compact_text.pack(fill="both", expand=True)
        scrollbar.config(command=self.compact_text.yview)

        for color, (ctype, disp_color) in chat_colors.items():
            self.compact_text.tag_config(ctype, foreground=disp_color)

        self.update_compact_messages()
        self.toggle_click_through()

    # ============================================================
    #   コンパクトモード：ドラッグ移動
    # ============================================================
    def start_move(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def do_move(self, event):
        x = self.compact_window.winfo_x() + event.x - self._drag_x
        y = self.compact_window.winfo_y() + event.y - self._drag_y
        self.compact_window.geometry(f"+{x}+{y}")

    # ============================================================
    #   コンパクトモード：リサイズ
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
    #   コンパクトモード：戻る
    # ============================================================
    def restore_main_window(self):
        self.compact_mode.set(False)
        self.toggle_mode()

    # ============================================================
    #   コンパクトモード：タブ切り替え
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
    #   コンパクトモード：フル再描画
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
#   ファイル監視（差分描画＋NG/SP最適化）
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

                    if text.startswith("経験値が") or text.startswith("ルーン経験値が") or text.startswith("[ELSO") or text.startswith("ペットが"):
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
    viewer = ChatViewer(root)
    root.mainloop()