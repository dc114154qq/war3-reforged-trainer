"""Campaign/cache extraction UI; all Tk access stays on the UI thread."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
from queue import Empty, Queue
import threading
from tkinter import StringVar, filedialog, messagebox, ttk

from war3_save_codes import SaveExtractionError
from war3_save_extraction_ui import SaveExtractionTab
from war3_services.archive_fields import (
    display_rows,
    export_archive_result,
    find_archive_files,
    read_archive_file,
    read_current_heroes,
)
from war3_services.save_extraction import documents_directory, log_extraction_failure


class ArchiveFieldsTab(ttk.Frame):
    def __init__(
        self,
        notebook,
        *,
        get_trainer=None,
        start_thread=None,
        operation_lock=None,
        get_language=lambda: "zh",
        is_closing=lambda: False,
    ):
        super().__init__(notebook, padding=8)
        notebook.add(self, text="存档提取")
        self.notebook = notebook
        self.get_trainer, self.start_thread = get_trainer, start_thread
        self.operation_lock, self.get_language, self.is_closing = (
            operation_lock,
            get_language,
            is_closing,
        )
        self.events, self.cancel = Queue(), threading.Event()
        self.busy, self.result = False, None
        self.files, self.rows, self.actions, self.translations = [], (), [], []
        self.directory = StringVar(self, str(documents_directory() / "Warcraft III"))
        self.file_path, self.detail, self.status = (
            StringVar(self),
            StringVar(self),
            StringVar(self),
        )
        self._status = (
            "先扫描目录或选择文件；读当前英雄前，请在游戏中载入存档并选中英雄。",
            "Scan a folder or choose a file. To read current heroes, load the save and select them in the game.",
        )
        self.panes = ttk.Notebook(self)
        self.panes.pack(fill="both", expand=True)
        page = ttk.Frame(self.panes, padding=8)
        self.panes.add(page, text="战役存档／英雄")
        self.page = page
        description = self._label(
            page,
            "读取战役的 .w3v 缓存（含自定义战役），或 .w3z 中保存的继承缓存：英雄属性、物品和章节字段。缓存可能早于当前状态；载入后可另读当前英雄。导出是查看与备份，不会自动导入或修改存档。",
            "Read campaign .w3v caches, including custom campaigns or inheritance caches inside .w3z saves: unit stats, items and chapter fields. A cache may predate current state; load the save to read current heroes. Export is for viewing and backup, without importing or editing saves.",
            wraplength=1000,
        )
        description.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        description.bind(
            "<Configure>", lambda e: description.configure(wraplength=max(150, e.width))
        )
        controls = ttk.Frame(page)
        controls.grid(row=1, column=0, sticky="ew", pady=4)
        self._label(controls, "存档目录", "Save folder").grid(row=0, column=0)
        ttk.Entry(controls, textvariable=self.directory).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        self._button(controls, "选择目录", "Choose folder", self.choose_directory).grid(
            row=0, column=2, padx=3
        )
        self._button(controls, "扫描存档文件", "Find saves", self.scan_directory).grid(
            row=0, column=3, padx=3
        )
        controls.columnconfigure(1, weight=1)
        self.file_tree = ttk.Treeview(
            page, columns=("name", "date", "path"), show="headings", height=4
        )
        for key, width in (("name", 200), ("date", 170), ("path", 680)):
            self.file_tree.column(key, width=width, minwidth=70)
        self.file_tree.grid(row=2, column=0, sticky="ew", pady=4)
        file_scroll = ttk.Scrollbar(
            page, orient="vertical", command=self.file_tree.yview
        )
        file_scroll.grid(row=2, column=1, sticky="ns")
        self.file_tree.configure(yscrollcommand=file_scroll.set)
        self.file_tree.bind("<<TreeviewSelect>>", self.select_file)
        self.file_tree.bind("<Double-1>", lambda _e: self.read_file())
        selected = ttk.Frame(page)
        selected.grid(row=3, column=0, sticky="ew", pady=4)
        ttk.Entry(selected, textvariable=self.file_path).grid(
            row=0, column=0, sticky="ew"
        )
        self._button(selected, "选择文件", "Choose file", self.choose_file).grid(
            row=0, column=1, padx=3
        )
        self._button(
            selected, "读取所选存档", "Read selected save", self.read_file
        ).grid(row=0, column=2, padx=3)
        self.live_button = self._button(
            selected, "读取当前选中英雄", "Read selected heroes", self.read_game
        )
        self.live_button.grid(row=0, column=3, padx=3)
        selected.columnconfigure(0, weight=1)
        table = ttk.Frame(page)
        table.grid(row=4, column=0, sticky="nsew", pady=4)
        self.tree = ttk.Treeview(
            table,
            columns=("scope", "key", "type", "value"),
            show="headings",
            selectmode="browse",
        )
        for key, width in (("scope", 280), ("key", 330), ("type", 85), ("value", 300)):
            self.tree.column(key, width=width, minwidth=65)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.show_detail)
        bottom = ttk.Frame(page)
        bottom.grid(row=5, column=0, sticky="ew", pady=4)
        self._button(
            bottom, "导出 JSON", "Export JSON", lambda: self.export(".json")
        ).pack(side="left", padx=3)
        self._button(
            bottom, "导出表格 CSV", "Export CSV", lambda: self.export(".csv")
        ).pack(side="left", padx=3)
        self._button(
            bottom, "复制所选字段", "Copy selected field", self.copy_selected
        ).pack(side="left", padx=3)
        ttk.Label(page, textvariable=self.detail, wraplength=1000).grid(
            row=6, column=0, sticky="ew"
        )
        ttk.Label(page, textvariable=self.status, wraplength=1000).grid(
            row=7, column=0, sticky="ew", pady=4
        )
        page.columnconfigure(0, weight=1)
        page.rowconfigure(4, weight=1)
        self.codes_tab = SaveExtractionTab(
            self.panes,
            get_trainer=get_trainer,
            start_thread=start_thread,
            operation_lock=operation_lock,
            get_language=get_language,
            is_closing=is_closing,
        )
        self.refresh_language()
        self.after(100, self._poll)

    def _text(self, zh, en):
        return zh if self.get_language() == "zh" else en

    def _label(self, parent, zh, en, **kwargs):
        widget = ttk.Label(parent, text=zh, justify="left", **kwargs)
        self.translations.append((widget, zh, en))
        return widget

    def _button(self, parent, zh, en, command):
        widget = ttk.Button(parent, text=zh, command=command)
        self.actions.append(widget)
        self.translations.append((widget, zh, en))
        return widget

    def _say(self, zh, en):
        self._status = (zh, en)
        self.status.set(self._text(zh, en))

    def refresh_language(self):
        self.notebook.tab(self, text=self._text("存档提取", "Save extraction"))
        for widget, zh, en in self.translations:
            widget.configure(text=self._text(zh, en))
        for key, zh, en in (
            ("name", "文件名", "File"),
            ("date", "保存时间", "Modified"),
            ("path", "文件位置", "Location"),
        ):
            self.file_tree.heading(key, text=self._text(zh, en))
        for key, zh, en in (
            ("scope", "来源／章节", "Source / chapter"),
            ("key", "字段", "Field"),
            ("type", "类型", "Type"),
            ("value", "值", "Value"),
        ):
            self.tree.heading(key, text=self._text(zh, en))
        self.panes.tab(
            self.page, text=self._text("战役存档／英雄", "Campaign saves / heroes")
        )
        self.codes_tab.refresh_language()
        self.panes.tab(self.codes_tab, text=self._text("RPG 存档码", "RPG save codes"))
        self.status.set(self._text(*self._status))
        if not self.busy and self.get_trainer is None:
            self.live_button.state(["disabled"])

    def _error(self, exc):
        from war3_error_messages import describe_error, format_error

        try:
            log_extraction_failure(exc)
        except OSError as log_error:
            exc.log_write_error = repr(log_error)
        self.status.set(describe_error(exc, self.get_language())["reason"])
        messagebox.showerror(
            self._text("错误", "Error"),
            format_error(exc, self.get_language()),
            parent=self.winfo_toplevel(),
        )

    def _start(self, kind, work, *, game=False):
        if self.busy or self.is_closing():
            return
        self.busy = True
        self.cancel.clear()
        for button in self.actions:
            button.state(["disabled"])
        if kind == "read":
            self.result = None
            self.rows = ()
            self.detail.set("")
            self.tree.delete(*self.tree.get_children())
        self._say("正在读取，请稍候。", "Reading, please wait.")

        def worker():
            try:
                with (
                    self.operation_lock
                    if game and self.operation_lock is not None
                    else nullcontext()
                ):
                    result = work()
                self.events.put((kind, result))
            except Exception as exc:
                self.events.put(("error", exc))

        try:
            if self.start_thread is not None:
                self.start_thread(worker, "war3-archive-fields")
            else:
                threading.Thread(
                    target=worker, name="war3-archive-fields", daemon=False
                ).start()
        except Exception as exc:
            self._finish()
            self._error(exc)

    def _finish(self):
        self.busy = False
        for button in self.actions:
            button.state(["!disabled"])
        if self.get_trainer is None:
            self.live_button.state(["disabled"])

    def _poll(self):
        if self.is_closing():
            self.cancel.set()
            return
        try:
            while True:
                kind, result = self.events.get_nowait()
                self._finish()
                if kind == "error":
                    self._error(result)
                elif kind == "files":
                    self._display_files(result)
                elif kind == "export":
                    self._say("已导出：" + result, "Exported: " + result)
                else:
                    self._display(result)
        except Empty:
            pass
        self.after(100, self._poll)

    def choose_directory(self):
        path = filedialog.askdirectory(
            parent=self.winfo_toplevel(), initialdir=self.directory.get()
        )
        if path:
            self.directory.set(path)

    def scan_directory(self):
        directory = self.directory.get()
        self._start("files", lambda: find_archive_files(directory, cancel=self.cancel))

    def _display_files(self, result):
        self.files = result["files"]
        self.file_tree.delete(*self.file_tree.get_children())
        for index, file in enumerate(self.files):
            date = datetime.fromtimestamp(file["modified_ns"] / 1e9).strftime(
                "%Y-%m-%d %H:%M"
            )
            self.file_tree.insert(
                "", "end", iid=str(index), values=(file["name"], date, file["path"])
            )
        if self.files:
            self.file_tree.selection_set("0")
            self.select_file()
        self._say(
            f"找到 {len(self.files)} 个存档／缓存文件，选择一个后读取。",
            f"Found {len(self.files)} save/cache files; select one to read.",
        )
        if not result["complete"]:
            self._say(
                self._status[0] + " 部分目录未扫描完。",
                self._status[1] + " Some folders were not fully scanned.",
            )
        if result.get("warnings"):
            error = SaveExtractionError("部分目录未能读取；已找到的文件仍可使用。")
            error.report = {
                "operation": "archive_file_scan",
                "warnings": result["warnings"],
            }
            try:
                log_extraction_failure(error)
            except OSError:
                pass

    def select_file(self, _event=None):
        selected = self.file_tree.selection()
        if selected:
            self.file_path.set(self.files[int(selected[0])]["path"])

    def choose_file(self):
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            initialdir=self.directory.get(),
            filetypes=(
                (
                    self._text("战役缓存／游戏存档", "Campaign caches / game saves"),
                    "*.w3v *.w3z",
                ),
            ),
        )
        if path:
            self.file_path.set(path)

    def read_file(self):
        path = self.file_path.get()
        if not path:
            self._error(SaveExtractionError("请先选择一个 .w3v 或 .w3z 文件。"))
            return
        self._start("read", lambda: read_archive_file(path))

    def read_game(self):
        try:
            if self.get_trainer is None:
                raise SaveExtractionError("请先连接游戏，再读取当前选中英雄。")
            host = self.get_trainer()
            if host is None:
                raise SaveExtractionError("请先连接游戏，再读取当前选中英雄。")
        except Exception as exc:
            self._error(exc)
            return
        self._start("read", lambda: read_current_heroes(host), game=True)

    def _display(self, result):
        self.result = result
        self.rows = display_rows(result)
        self.tree.delete(*self.tree.get_children())
        types = {
            "integer": "整数",
            "real": "小数",
            "boolean": "开关",
            "string": "文字",
            "hero": "单位",
            "item": "物品",
            "ability": "技能",
        }
        for index, row in enumerate(self.rows):
            shown = (
                row[0],
                row[1],
                types.get(row[2], row[2]) if self.get_language() == "zh" else row[2],
                str(row[3]),
            )
            self.tree.insert("", "end", iid=str(index), values=shown)
        if self.rows:
            self.tree.selection_set("0")
            self.show_detail()
        heroes = len(result.get("heroes", result.get("live_heroes", ())))
        zh = f"已读取 {len(self.rows)} 个展示字段，{heroes} 个保存单位／当前英雄。"
        en = f"Read {len(self.rows)} displayed fields and {heroes} stored units / current heroes."
        if result["source_kind"] == "loaded_game_snapshot":
            zh += " 来源：当前已载入游戏；不会写回游戏。"
            en += " Source: the currently loaded game; no game data was written."
        else:
            zh += " 来源：保存时的战役缓存，不等于当前英雄状态。"
            en += (
                " Source: saved campaign cache, which may differ from the current hero."
            )
        if not result.get("complete", True):
            error = SaveExtractionError(
                "部分英雄属性／背包／装备／天赋未能读取，已读出的字段仍可导出。"
            )
            error.report = {
                "operation": "archive_live_heroes",
                "warnings": result.get("warnings", ()),
            }
            try:
                path = log_extraction_failure(error)
                zh += f" 部分字段未读出，诊断日志：{path}"
                en += f" Some fields were unavailable; diagnostic log: {path}"
            except OSError:
                zh += " 部分字段未读出；日志保存失败。"
                en += " Some fields were unavailable; logging failed."
        if not self.rows:
            zh += " 该文件未保存英雄或进度字段，可尝试其他文件。"
            en += " This file has no stored unit/progress fields; try another file."
        self._say(zh, en)

    def show_detail(self, _event=None):
        selected = self.tree.selection()
        self.detail.set(
            " | ".join(str(value) for value in self.rows[int(selected[0])])
            if selected
            else ""
        )

    def copy_selected(self):
        self.show_detail()
        if self.detail.get():
            self.clipboard_clear()
            self.clipboard_append(self.detail.get())

    def export(self, suffix):
        if self.result is None:
            self._error(SaveExtractionError("请先读取存档或当前英雄，再导出。"))
            return
        result = self.result
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            defaultextension=suffix,
            initialfile="战役存档提取-"
            + datetime.now().strftime("%Y%m%d-%H%M%S")
            + suffix,
            filetypes=(("JSON" if suffix == ".json" else "CSV", "*" + suffix),),
        )
        if path:
            self._start("export", lambda: export_archive_result(path, result))
