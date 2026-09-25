"""Offline equipment reference tab; no connection or game mutations."""
from tkinter import StringVar, ttk

from war3_new_equipment_catalog import EQUIPMENT


def search_equipment(query, entries=EQUIPMENT):
    terms = query.casefold().split()
    return tuple(row for row in entries if all(term in (
        row['code'] + ' ' + row['name'] + ' ' + row['description']).casefold() for term in terms))


class NewEquipmentTab(ttk.Frame):
    def __init__(self, notebook):
        super().__init__(notebook, padding=10)
        notebook.add(self, text='3.0新装备')
        self.query = StringVar(self)
        self.count = StringVar(self)
        self.detail = StringVar(self, '选择装备可查看完整效果；双击行可复制物品代码。')
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        ttk.Label(bar, text='搜索名称、代码或效果').pack(side='left')
        ttk.Entry(bar, textvariable=self.query, width=36).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(bar, text='清空', command=lambda: self.query.set('')).pack(side='left', padx=4)
        ttk.Button(bar, text='复制代码', command=self.copy_code).pack(side='left', padx=4)
        ttk.Label(bar, textvariable=self.count).pack(side='right', padx=8)
        table = ttk.Frame(self)
        table.grid(row=1, column=0, sticky='nsew')
        self.tree = ttk.Treeview(table, columns=('name', 'code', 'description'), show='headings', selectmode='browse')
        for key, label, width in (('name', '物品名称', 240), ('code', '物品代码', 90), ('description', '物品效果描述', 630)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=70, stretch=key != 'code', anchor='w')
        self.tree.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        hscroll = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        hscroll.grid(row=1, column=0, sticky='ew')
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=hscroll.set)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        details = ttk.LabelFrame(self, text='完整效果描述', padding=8)
        details.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        label = ttk.Label(details, textvariable=self.detail, justify='left', anchor='nw', wraplength=950)
        label.pack(fill='both', expand=True)
        details.bind('<Configure>', lambda e: label.configure(wraplength=max(120, e.width - 24)))
        ttk.Label(self, text='来源：文档中的《被遗忘的王国》战役与 3.0.0.24268 中文物品数据。'
                  '仅列入战役明确引用的新装备；目录不保证其他地图支持生成。', wraplength=1000).grid(row=3, column=0, sticky='ew', pady=8)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.bind('<<TreeviewSelect>>', self.show_detail)
        self.tree.bind('<Double-1>', self.double_click)
        self.tree.bind('<Control-c>', lambda _event: self.copy_code())
        self.query.trace_add('write', lambda *_: self.refresh())
        self.refresh()

    def refresh(self):
        self.rows = search_equipment(self.query.get())
        for key in self.tree.get_children():
            self.tree.delete(key)
        for i, row in enumerate(self.rows):
            self.tree.insert('', 'end', iid=str(i), values=(row['name'], row['code'], ' / '.join(row['description'].splitlines())))
        self.count.set(f'{len(self.rows)} / {len(EQUIPMENT)} 件')
        self.detail.set('选择装备可查看完整效果；双击行可复制物品代码。')

    def selected(self):
        selection = self.tree.selection()
        return self.rows[int(selection[0])] if selection else None

    def show_detail(self, _event=None):
        row = self.selected()
        if row:
            self.detail.set(f"{row['name']}  [{row['code']}]\n{row['description']}\n来源章节：{'、'.join(row['chapters'])}")

    def copy_code(self):
        row = self.selected()
        if row:
            self.clipboard_clear()
            self.clipboard_append(row['code'])

    def double_click(self, event):
        key = self.tree.identify_row(event.y)
        if key:
            self.tree.selection_set(key)
            self.copy_code()
