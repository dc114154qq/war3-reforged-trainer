"""Six editable codes; persistence and game operations belong to other layers."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from war3_artifact_plan import ArtifactPlanError, DEFAULT_ARTIFACT_CODES


class ArtifactPlanPanel(ttk.Frame):
    def __init__(self, parent, *, settings, on_apply, get_language=lambda: 'zh'):
        super().__init__(parent, padding=12)
        self.settings, self.on_apply, self.get_language = settings, on_apply, get_language
        self._updating = False
        self._texts = []
        self._edited = False
        self.columnconfigure(0, weight=1)
        self.help = self._label(
            '每格填写4位物品代码，区分大小写。修改正确后立即自动保存，下次打开会保留。按钮和 Ctrl+Num3 共用此方案。',
            'Enter a case-sensitive four-character item code in each slot. Valid edits are saved immediately and restored next time. The button and Ctrl+Num3 use this same plan.', 0)
        self.slots = ttk.Frame(self)
        self.slots.grid(row=1, column=0, sticky='ew', pady=(8, 6))
        self.variables, self.slot_frames, self.slot_labels, self.entries = [], [], [], []
        for index, code in enumerate(settings.displayed_plan.codes):
            frame = ttk.Frame(self.slots, padding=8)
            frame.columnconfigure(1, weight=1)
            label = ttk.Label(frame)
            label.grid(row=0, column=0, sticky='w', padx=(0, 8))
            variable = tk.StringVar(master=self, value=code)
            entry = ttk.Entry(frame, textvariable=variable, width=14)
            entry.grid(row=0, column=1, sticky='ew')
            variable.trace_add('write', self._changed)
            self.variables.append(variable)
            self.slot_frames.append(frame)
            self.slot_labels.append(label)
            self.entries.append(entry)
        controls = ttk.Frame(self)
        controls.grid(row=2, column=0, sticky='w', pady=(6, 8))
        self.apply_button = self._text(ttk.Button(controls, command=self.apply_clicked), '一键神器', 'Apply six-slot plan')
        self.apply_button.pack(side='left')
        self.reset_button = self._text(ttk.Button(controls, command=self.reset_clicked), '恢复默认方案', 'Restore default plan')
        self.reset_button.pack(side='left', padx=(10, 0))
        self.status = ttk.Label(self, justify='left')
        self.status.grid(row=3, column=0, sticky='ew', pady=(2, 6))
        self.notice = self._label('执行时会替换选中单位的六格物品栏；请填写当前地图中存在的物品代码。',
                                 "Applying replaces all six inventory slots of the selected units. Use item codes defined in the current map.", 4)
        self.bind('<Configure>', self._layout)
        self.refresh_language()

    def _text(self, widget, zh, en):
        self._texts.append((widget, zh, en))
        return widget

    def _label(self, zh, en, row):
        label = self._text(ttk.Label(self, justify='left'), zh, en)
        label.grid(row=row, column=0, sticky='ew', pady=(4, 2))
        return label

    def _layout(self, event=None):
        width = max(240, self.winfo_width() - 24)
        columns = 3 if width >= 750 else 2
        for col in range(3):
            self.slots.columnconfigure(col, weight=1 if col < columns else 0, uniform='artifact-slots')
        for index, frame in enumerate(self.slot_frames):
            frame.grid(row=index // columns, column=index % columns, sticky='ew', padx=(0, 8), pady=3)
        for label in (self.help, self.status, self.notice):
            label.configure(wraplength=width)

    def _changed(self, *_):
        if self._updating:
            return
        self._edited = True
        try:
            self.settings.update(tuple(variable.get() for variable in self.variables))
        except ArtifactPlanError:
            pass
        self.refresh_status()

    def refresh_status(self):
        english = self.get_language() == 'en'
        error = self.settings.error or self.settings.load_error
        if error is not None:
            text = error.message('en' if english else 'zh')
        elif self.settings.saved:
            text = ('Plan saved. It will be restored next time.' if english else '方案已保存，下次打开会自动载入。') if self._edited else (
                    'Last saved plan loaded.' if english else '已载入上次保存的方案。')
        else:
            text = ('Using the original default plan. Valid edits are saved automatically.' if english else '当前为原来的默认方案；修改正确后会自动保存。')
        self.status.configure(text=text)
        error = self.settings.error
        for index, entry in enumerate(self.entries, 1):
            entry.state(['invalid'] if error is not None and error.slot == index else ['!invalid'])

    def reset_clicked(self):
        try:
            self.settings.update(DEFAULT_ARTIFACT_CODES)
        except ArtifactPlanError:
            self.refresh_status()
            return
        self._updating = True
        try:
            for variable, code in zip(self.variables, DEFAULT_ARTIFACT_CODES):
                variable.set(code)
        finally:
            self._updating = False
        self._edited = True
        self.refresh_status()

    def apply_clicked(self):
        try:
            plan = self.settings.snapshot()
        except ArtifactPlanError as exc:
            self.refresh_status()
            english = self.get_language() == 'en'
            messagebox.showerror('Item plan' if english else '装备方案', exc.message('en' if english else 'zh'), parent=self)
            return
        # Captured on the GUI thread; later edits do not alter a queued request.
        self.on_apply(plan)

    def refresh_language(self):
        english = self.get_language() == 'en'
        for widget, zh, en in self._texts:
            widget.configure(text=en if english else zh)
        for index, label in enumerate(self.slot_labels, 1):
            label.configure(text=f'Slot {index}' if english else f'槽位 {index}')
        self.refresh_status()
        self._layout()
