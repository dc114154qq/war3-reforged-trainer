"""Searchable reference for official 3.0 campaign hero skills."""
from tkinter import StringVar, ttk

from war3_hero_skill_catalog import HEROES, SKILLS

ALL_HEROES = '全部角色'


def search_skills(query, hero='', entries=SKILLS):
    terms = query.casefold().split()
    return tuple(row for row in entries if (not hero or hero == ALL_HEROES or row['hero'] == hero) and
                 all(term in (row['hero'] + ' ' + row['unit_code'] + ' ' +
                              row['name'] + ' ' + row['code'] + ' ' +
                              row['description']).casefold() for term in terms))


class HeroSkillTab(ttk.Frame):
    def __init__(self, notebook):
        super().__init__(notebook, padding=10)
        notebook.add(self, text='3.0新角色技能')
        self.query = StringVar(self)
        self.hero = StringVar(self, ALL_HEROES)
        self.count = StringVar(self)
        self.detail = StringVar(self, '选择技能可查看完整效果；双击行可复制技能代码。')
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        ttk.Label(bar, text='角色').pack(side='left')
        hero_picker = ttk.Combobox(bar, textvariable=self.hero, state='readonly', width=18,
                                   values=(ALL_HEROES,) + tuple(name for _, name in HEROES))
        hero_picker.pack(side='left', padx=(6, 12))
        hero_picker.bind('<<ComboboxSelected>>', lambda _event: self.refresh())
        ttk.Label(bar, text='搜索技能、代码或效果').pack(side='left')
        ttk.Entry(bar, textvariable=self.query, width=36).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(bar, text='清空', command=self.clear).pack(side='left', padx=4)
        ttk.Button(bar, text='复制代码', command=self.copy_code).pack(side='left', padx=4)
        ttk.Label(bar, textvariable=self.count).pack(side='right', padx=8)

        table = ttk.Frame(self)
        table.grid(row=1, column=0, sticky='nsew')
        columns = ('hero', 'name', 'code', 'levels', 'description')
        self.tree = ttk.Treeview(table, columns=columns, show='headings', selectmode='browse')
        for key, label, width in (('hero', '角色', 150), ('name', '技能', 190),
                                  ('code', '技能代码', 95), ('levels', '等级', 62),
                                  ('description', '效果', 580)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=55, stretch=key == 'description', anchor='w')
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
        label = ttk.Label(details, textvariable=self.detail, justify='left', anchor='nw', wraplength=900)
        label.pack(fill='both', expand=True)
        details.bind('<Configure>', lambda event: label.configure(wraplength=max(120, event.width - 24)))
        ttk.Label(self, text='技能取自官方 3.0 战役英雄的技能列表；不同地图可能修改同代码的效果。',
                  wraplength=900).grid(row=3, column=0, sticky='ew', pady=8)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.bind('<<TreeviewSelect>>', self.show_detail)
        self.tree.bind('<Double-1>', self.double_click)
        self.tree.bind('<Control-c>', lambda _event: self.copy_code())
        self.query.trace_add('write', lambda *_: self.refresh())
        self.refresh()

    def clear(self):
        self.hero.set(ALL_HEROES)
        self.query.set('')
        self.refresh()

    def refresh(self):
        self.rows = search_skills(self.query.get(), self.hero.get())
        for key in self.tree.get_children():
            self.tree.delete(key)
        for index, row in enumerate(self.rows):
            self.tree.insert('', 'end', iid=str(index), values=(
                row['hero'], row['name'], row['code'], row['levels'],
                ' / '.join(row['description'].splitlines())))
        self.count.set(f'{len(self.rows)} / {len(SKILLS)} 项')
        self.detail.set('选择技能可查看完整效果；双击行可复制技能代码。')

    def selected(self):
        selection = self.tree.selection()
        return self.rows[int(selection[0])] if selection else None

    def show_detail(self, _event=None):
        row = self.selected()
        if row:
            self.detail.set(f"{row['hero']}  [{row['unit_code']}]  {row['name']}  [{row['code']}]\n"
                            f"{row['description']}")

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
