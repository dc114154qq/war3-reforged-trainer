"""Save-code extraction tab. Worker results enter Tk only through a polled queue."""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
import threading
from tkinter import StringVar, Text, filedialog, messagebox, ttk

from war3_save_codes import SaveExtractionError, extract_text, validate_prefix
from war3_services.save_extraction import (
    default_save_roots, documents_directory, export_codes, log_extraction_failure,
    read_code_file, read_live_codes, scan_code_directory,
)


class SaveExtractionTab(ttk.Frame):
    def __init__(self, notebook, *, get_trainer=None, start_thread=None, operation_lock=None,
                 get_language=lambda: "zh", is_closing=lambda: False):
        super().__init__(notebook, padding=10)
        notebook.add(self, text="存档提取")
        self.get_trainer, self.start_thread, self.operation_lock = get_trainer, start_thread, operation_lock
        self.get_language, self.is_closing = get_language, is_closing
        self.events = Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.rows = []
        self._message = ("先在地图里生成存档码，再读取文件或扫描游戏；存档码不会自动输入游戏。",
                         "Generate a save code in the map first, then read its file or scan the game. No command is sent to the game.")
        self.status = StringVar(self)
        self.detail = StringVar(self)
        self.prefix = StringVar(self, "-load")
        roots = default_save_roots()
        self.directory = StringVar(self, str(roots[0] if roots else documents_directory() / "Warcraft III" / "CustomMapData"))
        self.actions = []
        description = ttk.Label(self, text="提取 RPG 地图生成的存档码，方便复制后下次载入。码是否有效由原地图判断；整局 W3Z 存档不能通用转换成 RPG 存档码。",
                                wraplength=1050, justify="left")
        description.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        description.bind("<Configure>", lambda e: description.configure(wraplength=max(150, e.width)))
        files = ttk.Frame(self)
        files.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(files, text="存档码目录").grid(row=0, column=0, sticky="w")
        ttk.Entry(files, textvariable=self.directory).grid(row=0, column=1, sticky="ew", padx=8)
        self._button(files, "选择目录", self.choose_directory, 0, 2)
        self._button(files, "扫描目录", self.scan_directory, 0, 3)
        self._button(files, "读取文件", self.read_file, 0, 4)
        files.columnconfigure(1, weight=1)
        controls = ttk.Frame(self)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(controls, text="地图载入指令").pack(side="left")
        ttk.Entry(controls, textvariable=self.prefix, width=14).pack(side="left", padx=8)
        live = ttk.Button(controls, text="读取游戏内存档码", command=self.scan_game)
        live.pack(side="left", padx=4); self.actions.append(live)
        self.live_button = live
        if get_trainer is None:
            live.state(["disabled"])
        self.cancel_button = ttk.Button(controls, text="停止提取", command=self.cancel.set, state="disabled")
        self.cancel_button.pack(side="left", padx=4)
        paste = ttk.LabelFrame(self, text="也可粘贴聊天文字或存档文件内容", padding=6)
        paste.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.input = Text(paste, height=4, wrap="word")
        self.input.pack(side="left", fill="both", expand=True)
        side = ttk.Frame(paste); side.pack(side="left", padx=8)
        extract = ttk.Button(side, text="提取粘贴内容", command=self.scan_paste)
        extract.pack(fill="x", pady=3); self.actions.append(extract)
        ttk.Button(side, text="清空输入", command=lambda: self.input.delete("1.0", "end")).pack(fill="x", pady=3)
        table = ttk.Frame(self)
        table.grid(row=4, column=0, sticky="nsew")
        self.tree = ttk.Treeview(table, columns=("kind", "code", "source"), show="headings", selectmode="browse")
        for key, title, width in (("kind", "提取类型", 130), ("code", "存档码 / 载入指令", 550), ("source", "来源文件", 300)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=70, stretch=key != "kind")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        table.rowconfigure(0, weight=1); table.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.show_detail)
        self.tree.bind("<Control-c>", lambda _e: self.copy_selected())
        bottom = ttk.Frame(self)
        bottom.grid(row=5, column=0, sticky="ew", pady=8)
        ttk.Button(bottom, text="复制载入指令", command=self.copy_selected).pack(side="left", padx=(0, 6))
        ttk.Button(bottom, text="复制原始码", command=lambda: self.copy_selected(raw=True)).pack(side="left", padx=6)
        self.export_button = ttk.Button(bottom, text="导出提取结果", command=self.export)
        self.export_button.pack(side="left", padx=6); self.actions.append(self.export_button)
        ttk.Label(self, textvariable=self.detail, wraplength=1050, justify="left").grid(row=6, column=0, sticky="ew")
        ttk.Label(self, textvariable=self.status, wraplength=1050, justify="left").grid(row=7, column=0, sticky="ew", pady=(8, 0))
        self.rowconfigure(4, weight=1); self.columnconfigure(0, weight=1)
        self.refresh_language()
        self.after(100, self._poll)

    def _button(self, parent, text, command, row, column):
        button = ttk.Button(parent, text=text, command=command)
        button.grid(row=row, column=column, padx=4)
        self.actions.append(button)

    def _say(self, zh, en):
        self._message = (zh, en)
        self.status.set(self._message[1 if self.get_language() == "en" else 0])

    def refresh_language(self):
        self.status.set(self._message[1 if self.get_language() == "en" else 0])
        for i, row in enumerate(self.rows):
            if self.tree.exists(str(i)):
                self.tree.item(str(i), values=(self._kind(row), row.command or row.code, row.source))
        self.show_detail()

    def _kind(self, row):
        if row.kind == "fragment":
            return "原始片段" if self.get_language() == "zh" else "Raw fragment"
        return "存档码候选" if self.get_language() == "zh" else "Code candidate"

    def _error(self, exc):
        from war3_error_messages import describe_error, format_error
        try:
            log_extraction_failure(exc)
        except Exception as error:
            exc.log_write_error = repr(error)
        messagebox.showerror("错误" if self.get_language() == "zh" else "Error",
                             format_error(exc, self.get_language()), parent=self.winfo_toplevel())
        self.status.set(describe_error(exc, self.get_language())["reason"])

    def _start(self, work, *, game=False):
        if self.busy or self.is_closing():
            return
        self.busy = True; self.cancel.clear()
        for button in self.actions:
            button.state(["disabled"])
        self.cancel_button.state(["!disabled"])
        self._say("正在提取，可随时停止；其他游戏功能不受本次提取结果影响。",
                  "Extracting; you can stop at any time. The result does not block other game operations.")

        def worker():
            try:
                with self.operation_lock if game and self.operation_lock is not None else nullcontext():
                    result = work()
                self.events.put(("result", result))
            except Exception as exc:
                if not game and isinstance(exc, OSError):
                    original = exc
                    exc = SaveExtractionError("存档码文件或导出目录访问失败，请检查路径、文件占用和目录权限。")
                    exc.__cause__ = original
                self.events.put(("error", exc))

        try:
            if self.start_thread is not None:
                self.start_thread(worker, "war3-save-extraction")
            else:
                threading.Thread(target=worker, name="war3-save-extraction", daemon=False).start()
        except Exception as exc:
            self._finish(); self._error(exc)

    def _finish(self):
        self.busy = False
        for button in self.actions:
            button.state(["!disabled"])
        if self.get_trainer is None:
            self.live_button.state(["disabled"])
        self.cancel_button.state(["disabled"])

    def _progress(self, result):
        self.events.put(("progress", result))

    def _poll(self):
        if self.is_closing():
            self.cancel.set()
            return
        try:
            while True:
                kind, result = self.events.get_nowait()
                if kind == "progress":
                    self._say(f"已读取 {result.get('bytes', 0) / 1048576:.1f} MB，找到 {result.get('candidates', 0)} 个候选。",
                              f"Read {result.get('bytes', 0) / 1048576:.1f} MB; found {result.get('candidates', 0)} candidates.")
                elif kind == "error":
                    self._finish(); self._error(result)
                else:
                    self._finish(); self._display(result)
        except Empty:
            pass
        self.after(100, self._poll)

    def _display(self, result):
        if "exported" in result:
            self._say("已导出提取结果：" + str(result["exported"]), "Exported results: " + str(result["exported"]))
            return
        self.rows = list(result.get("codes", ()))
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, row in enumerate(self.rows):
            self.tree.insert("", "end", iid=str(i), values=(self._kind(row), row.command or row.code, row.source))
        if self.rows:
            self.tree.selection_set("0"); self.show_detail()
        else:
            self.detail.set("")
        partial = not result.get("complete", True)
        reason = result.get("stop_reason", "")
        limits = {"time_limit": ("扫描时间已到，可再试一次或改读存档码文件。", "Scan time limit reached; retry or read the save-code file."),
                  "size_limit": ("扫描容量已到，未扫描全部内存。", "Scan size limit reached; not all memory was scanned."),
                  "cancelled": ("已停止提取。", "Extraction stopped.")}
        zh, en = limits.get(reason, ("部分文件或内存未读出。" if partial else "读取已完成。",
                                     "Some files or memory could not be read." if partial else "Read completed."))
        warnings = result.get("warnings", ())
        if warnings:
            # Detailed file errors stay in the saved diagnostic report.
            error = SaveExtractionError("部分存档码文件未能读取；已提取的结果仍可复制，其余游戏操作可继续。")
            error.report = {"operation": "save_extraction", "file_failures": warnings}
            try:
                path = log_extraction_failure(error)
                zh += f" {len(warnings)} 个文件未读出，诊断日志：{path}"
                en += f" {len(warnings)} files failed; diagnostic log: {path}"
            except OSError:
                zh += " 诊断日志未能保存。"; en += " Diagnostic log could not be saved."
        if not self.rows:
            zh += " 没有找到明确的存档码，请先在游戏里按地图说明保存，再读取文件或扫描。"
            en += " No explicit save code found. Save in the map first, then read its file or scan."
        self._say(f"找到 {len(self.rows)} 个存档码或片段。" + zh,
                  f"Found {len(self.rows)} code candidates or fragments. " + en)

    def choose_directory(self):
        path = filedialog.askdirectory(parent=self.winfo_toplevel(), initialdir=documents_directory(),
            title="选择存档码目录" if self.get_language() == "zh" else "Choose save-code directory")
        if path:
            self.directory.set(path)

    def scan_directory(self):
        path, prefix = self.directory.get(), self.prefix.get()
        self._start(lambda: scan_code_directory(path, prefix, cancel=self.cancel, progress=self._progress))

    def read_file(self):
        path = filedialog.askopenfilename(parent=self.winfo_toplevel(), initialdir=documents_directory(),
            filetypes=(("Save-code files", "*.txt *.pld *.log *.j *.lua"), ("All files", "*.*")))
        if path:
            prefix = self.prefix.get()
            self._start(lambda: {"codes": read_code_file(path, prefix), "complete": True})

    def scan_paste(self):
        text, prefix = self.input.get("1.0", "end-1c"), self.prefix.get()
        self._start(lambda: {"codes": extract_text(text, "粘贴内容", prefix), "complete": True})

    def scan_game(self):
        try:
            prefix = validate_prefix(self.prefix.get())
            if self.get_trainer is None:
                raise SaveExtractionError("请先连接正确的 Warcraft III 游戏进程。")
            host = self.get_trainer()
        except Exception as exc:
            self._error(exc); return
        self._start(lambda: read_live_codes(host, prefix, cancel=self.cancel, progress=self._progress), game=True)

    def selected(self):
        items = self.tree.selection()
        return self.rows[int(items[0])] if items else None

    def show_detail(self, _event=None):
        row = self.selected()
        if row is None:
            return
        if self.get_language() == "en":
            text = ("A raw fragment is not a complete load command. The map decides how to combine it."
                    if row.kind == "fragment" else "Candidate read successfully; validity, player binding and recency must be checked by the original map.")
            self.detail.set(f"{row.command or row.code}\nSource: {row.source}\n{text}")
        else:
            text = ("这是原始片段，不是完整载入指令，拼接规则由地图决定。" if row.kind == "fragment" else
                    "已读出候选；是否有效、属于哪个玩家、是不是最新存档，以原地图载入结果为准。")
            self.detail.set(f"{row.command or row.code}\n来源：{row.source}\n{text}")

    def copy_selected(self, raw=False):
        try:
            row = self.selected()
            if row is None:
                raise SaveExtractionError("请先在提取结果中选择一条存档码。")
            if not raw and not row.command:
                raise SaveExtractionError("这条是原始片段，没有完整载入指令；可使用“复制原始码”。")
            self.clipboard_clear(); self.clipboard_append(row.code if raw else row.command)
            self._say("已复制，请回到原地图按它的载入规则使用。", "Copied. Use the original map's load procedure.")
        except Exception as exc:
            self._error(exc)

    def export(self):
        if not self.rows:
            self._error(SaveExtractionError("尚未提取到存档码，请先读取文件、粘贴文本或扫描游戏。")); return
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), defaultextension=".txt",
            initialfile="存档码提取-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".txt",
            filetypes=(("Text", "*.txt"), ("JSON", "*.json")))
        if path:
            rows = tuple(self.rows)
            self._start(lambda: {"exported": export_codes(path, rows)})
