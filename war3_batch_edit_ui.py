"""Batch editing tab. All game access belongs to BatchEditService."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from war3_services.batch_edit import BatchEditModel, BatchEditService


class BatchEditTab:
    def __init__(self, notebook, *, get_trainer, call_async, ui_text, logger_factory):
        self.frame = ttk.Frame(notebook, padding=10)
        self.get_trainer, self.call_async = get_trainer, call_async
        self.ui_text, self.logger_factory = ui_text, logger_factory
        self.model = None
        self.targets = {}
        self.busy = False
        self.result = None
        self.labels = []
        self.summary = tk.StringVar(master=self.frame)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(2, weight=1)
        toolbar = ttk.Frame(self.frame)
        toolbar.grid(row=0, column=0, sticky="ew")
        self.read_button = self._button(toolbar, "读取所有选中单位", self.read_clicked)
        self.all_button = self._button(toolbar, "全选", lambda: self.select_all(True))
        self.none_button = self._button(toolbar, "全不选", lambda: self.select_all(False))
        self.write_button = self._button(toolbar, "批量修改", self.write_clicked)
        self.clear_button = self._button(toolbar, "清空全部目标值", self.clear_targets)
        hint = ttk.Label(
            self.frame,
            text=self.ui_text("单击单位代码切换勾选；只修改填写了目标值的字段，其他字段保持原值。"),
            wraplength=990,
        )
        hint.grid(row=1, column=0, sticky="w", pady=(8, 6))
        self.labels.append((hint, "单击单位代码切换勾选；只修改填写了目标值的字段，其他字段保持原值。"))
        panes = ttk.Panedwindow(self.frame, orient="horizontal")
        panes.grid(row=2, column=0, sticky="nsew")
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.units = ttk.Treeview(
            left, columns=("checked", "rawcode", "instance", "hp", "mp"),
            show="headings", selectmode="browse", height=12,
        )
        self.unit_headings = (("checked", "勾选", 45), ("rawcode", "单位代码", 82),
                              ("instance", "单位实例", 130), ("hp", "生命", 90),
                              ("mp", "魔法", 90))
        for key, label, width in self.unit_headings:
            self.units.heading(key, text=self.ui_text(label))
            self.units.column(key, width=width, minwidth=40, stretch=key in {"hp", "mp"})
        self.units.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.units.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.units.configure(yscrollcommand=scroll.set)
        self.units.bind("<Button-1>", self.toggle_clicked)
        self.units.bind("<space>", self.toggle_focused)
        # A visible input for every writable field; blank means no request.
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(right, highlightthickness=0, borderwidth=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        field_scroll = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        field_scroll.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=field_scroll.set)
        self.field_frame = ttk.Frame(self.canvas)
        self.field_window = self.canvas.create_window((0, 0), window=self.field_frame, anchor="nw")
        self.field_frame.bind("<Configure>", lambda _event: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(
            self.field_window, width=event.width))
        self.canvas.bind("<MouseWheel>", self.scroll_fields)
        ttk.Label(self.frame, textvariable=self.summary, wraplength=990).grid(
            row=3, column=0, sticky="w", pady=(8, 5))
        self.results = ttk.Treeview(
            self.frame, columns=("unit", "field", "target", "status", "reason"),
            show="headings", height=5,
        )
        self.result_headings = (("unit", "单位实例", 170), ("field", "字段", 160),
                               ("target", "目标值", 100), ("status", "结果", 75),
                               ("reason", "读回或跳过原因", 410))
        for key, label, width in self.result_headings:
            self.results.heading(key, text=self.ui_text(label))
            self.results.column(key, width=width, stretch=key == "reason")
        self.results.grid(row=4, column=0, sticky="nsew")
        result_scroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.results.yview)
        result_scroll.grid(row=4, column=1, sticky="ns")
        self.results.configure(yscrollcommand=result_scroll.set)
        self.refresh_language()

    def _button(self, parent, label, command):
        button = ttk.Button(parent, text=self.ui_text(label), command=command)
        button.pack(side="left", padx=(0, 8))
        self.labels.append((button, label))
        return button

    @staticmethod
    def rawcode(value):
        return value.to_bytes(4, "big").decode("ascii", errors="replace") if value else "?"

    def _post(self, callback, *args):
        self.frame.after(0, callback, *args)

    def _busy(self, busy):
        self.busy = busy
        for button in (self.read_button, self.write_button, self.all_button,
                       self.none_button, self.clear_button):
            button.state(["disabled"] if busy else ["!disabled"])

    def _start(self, action):
        if self.busy:
            return
        self._busy(True)

        def run():
            try:
                return action()
            finally:
                self._post(self._busy, False)
        try:
            self.call_async(run, "batch_edit")
        except Exception:
            self._busy(False)
            raise

    def read_clicked(self):
        self._start(self.read_data)

    def read_data(self):
        try:
            snapshot = BatchEditService(self.get_trainer(), self.logger_factory).read()
        except Exception:
            self._post(self.clear_snapshot)
            raise
        self._post(self.populate, snapshot)
        return self.ui_text(f"已读取批量单位 {len(snapshot.units)} 个")

    def clear_snapshot(self):
        self.model = None
        self.targets = {}
        self.result = None
        self.units.delete(*self.units.get_children())
        self.results.delete(*self.results.get_children())
        self.render_fields()
        self.update_summary()

    def populate(self, snapshot):
        self.model = BatchEditModel(snapshot)
        self.result = None
        self.targets = {}
        self.results.delete(*self.results.get_children())
        self.render_units()
        self.render_fields()
        self.update_summary()

    def render_units(self):
        focus = self.units.focus()
        self.units.delete(*self.units.get_children())
        if self.model:
            for index, unit in enumerate(self.model.snapshot.units):
                fields = {field.key: field for field in unit.fields}
                self.units.insert("", "end", iid=str(index), values=(
                    "☑" if unit.identity in self.model.checked else "☐",
                    self.rawcode(unit.ref.rawcode), f"#{index + 1} 0x{unit.ref.handle.value:x}",
                    fields["hp_current"].value_text() if "hp_current" in fields else "—",
                    fields["mp_current"].value_text() if "mp_current" in fields else "—",
                ))
        if focus and self.units.exists(focus):
            self.units.focus(focus)
            self.units.selection_set(focus)

    def toggle_clicked(self, event):
        if self.units.identify_region(event.x, event.y) == "cell":
            row = self.units.identify_row(event.y)
            if row and not self.busy:
                self.units.focus(row)
                self.toggle(row)
            return "break"

    def toggle_focused(self, _event=None):
        if self.units.focus() and not self.busy:
            self.toggle(self.units.focus())
        return "break"

    def toggle(self, row):
        if self.model:
            self.model.toggle(self.model.snapshot.units[int(row)].identity)
            self.render_units()
            self.update_summary()

    def select_all(self, checked):
        if self.model and not self.busy:
            self.model.select_all(checked)
            self.render_units()
            self.update_summary()

    def scroll_fields(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def render_fields(self):
        values = {key: value.get() for key, value in self.targets.items()}
        for widget in self.field_frame.winfo_children():
            widget.destroy()
        self.targets = {}
        for col, title in enumerate(("可修改字段", "类型", "支持单位数", "目标值（留空跳过）")):
            ttk.Label(self.field_frame, text=self.ui_text(title)).grid(
                row=0, column=col, sticky="w", padx=6, pady=5)
        if self.model:
            for row, option in enumerate(self.model.field_options(), 1):
                ttk.Label(self.field_frame, text=self.ui_text(
                    f"{option.category} / {option.label}")).grid(
                        row=row, column=0, sticky="w", padx=6, pady=3)
                ttk.Label(self.field_frame, text=option.value_type).grid(
                    row=row, column=1, sticky="w", padx=6)
                ttk.Label(self.field_frame, text=f"{option.supported}/{len(self.model.snapshot.units)}").grid(
                    row=row, column=2, sticky="w", padx=6)
                value = tk.StringVar(master=self.frame, value=values.get(option.key, ""))
                entry = ttk.Entry(self.field_frame, textvariable=value, width=17)
                entry.grid(row=row, column=3, sticky="ew", padx=6, pady=3)
                entry.bind("<MouseWheel>", self.scroll_fields)
                self.targets[option.key] = value
        self.field_frame.columnconfigure(3, weight=1)

    def clear_targets(self):
        if not self.busy:
            for value in self.targets.values():
                value.set("")

    def update_summary(self):
        if not self.model:
            self.summary.set(self.ui_text("尚未读取批量单位"))
        else:
            unread = sum(bool(unit.error) for unit in self.model.snapshot.units)
            self.summary.set(self.ui_text(
                f"已读取 {len(self.model.snapshot.units)} 个单位，已勾选 {len(self.model.checked)} 个；"
                f"可修改字段 {len(self.model.field_options())} 项，字段读取异常 {unread} 个单位。"))

    def write_clicked(self):
        model = self.model
        units = model.selected_units() if model else ()
        targets = {key: value.get() for key, value in self.targets.items()}

        def write():
            if model is None:
                raise ValueError("请先读取批量单位")
            result = BatchEditService(self.get_trainer(), self.logger_factory).apply(
                model.snapshot, units, targets)
            self._post(self.show_result, result)
            return self.result_summary(result)
        self._start(write)

    def result_summary(self, result):
        return self.ui_text(
            f"批量修改完成：成功 {result.count('success')} 项，跳过 {result.count('skipped')} 项，"
            f"失败 {result.count('failed')} 项，未执行 {result.count('not_attempted')} 项。"
            f"日志：{result.log_path}" + (f"；{result.stopped}" if result.stopped else ""))

    def show_result(self, result):
        self.result = result
        self.results.delete(*self.results.get_children())
        labels = {"success": "成功", "skipped": "跳过", "failed": "失败", "not_attempted": "未执行"}
        options = {option.key: option.label for option in self.model.field_options()} if self.model else {}
        for row in result.fields:
            self.results.insert("", "end", values=(
                f"{self.rawcode(row.unit.ref.rawcode)} 0x{row.unit.ref.handle.value:x}",
                self.ui_text(options.get(row.key, row.key)), row.target,
                self.ui_text(labels[row.status]), self.ui_text(row.reason or row.actual)))
        self.summary.set(self.result_summary(result))

    def refresh_language(self):
        for widget, label in self.labels:
            widget.configure(text=self.ui_text(label))
        for key, label, _width in self.unit_headings:
            self.units.heading(key, text=self.ui_text(label))
        for key, label, _width in self.result_headings:
            self.results.heading(key, text=self.ui_text(label))
        self.render_fields()
        if self.result:
            self.show_result(self.result)
        else:
            self.update_summary()
