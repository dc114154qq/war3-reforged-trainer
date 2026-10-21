"""Offline definition repair, with wrapping text and copyable complete paths."""
from __future__ import annotations
from pathlib import Path
import os, queue, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from war3_ui_services import get_ui_services


class ExtensionDefinitionPanel(ttk.Frame):
    def __init__(self,parent,*,get_language=lambda:'zh',start_thread=None,is_closing=lambda:False,services=None):
        super().__init__(parent)
        self.services=get_ui_services(parent,services)
        self.get_language=get_language;self.start_thread=start_thread;self.is_closing=is_closing
        self.dialog=None
        self.button=ttk.Button(self,command=self.open_dialog)
        self.help=ttk.Label(self,justify='left',wraplength=600)
        self.columnconfigure(1,weight=1)
        self.bind('<Configure>',self._layout)
        self.refresh_language()

    def _layout(self,event=None):
        width=max(1,self.winfo_width())
        if width<760:
            self.button.grid(row=0,column=0,columnspan=2,sticky='w')
            self.help.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(4,0))
            self.help.configure(wraplength=max(100,width-12))
        else:
            self.button.grid(row=0,column=0,columnspan=1,sticky='w')
            self.help.grid(row=0,column=1,columnspan=1,sticky='ew',padx=(10,0))
            self.help.configure(wraplength=max(100,width-self.button.winfo_reqwidth()-16))

    def refresh_language(self):
        english=self.get_language()=='en'
        self.button.configure(text='Add backpack definitions…' if english else '补齐战役／地图背包定义')
        self.help.configure(text=('If adding a backpack reports missing definitions, choose a campaign or map here. A new copy is created.'
                                  if english else '添加背包提示“背包装备未定义”时，点此选择战役或地图补齐定义，生成一份新副本。'))
        self._layout()
        if self.dialog is not None and self.dialog.winfo_exists():self.dialog.refresh_language()

    def open_dialog(self):
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.deiconify();self.dialog.lift();return
        self.dialog=DefinitionDialog(self)


class DefinitionDialog(tk.Toplevel):
    def __init__(self,panel):
        super().__init__(panel.winfo_toplevel())
        self.panel=panel;self.events=queue.Queue();self.cancel=threading.Event()
        self.busy=False;self.result=None;self.close_after=False;self._texts=[]
        self.status_message=('请选择战役或地图。处理时会逐章核验，原文件保留。',
                             'Choose a campaign or map. Each chapter is verified and the original is preserved.')
        self.minsize(500,420);self.geometry('780x690');self.transient(panel.winfo_toplevel())
        self.protocol('WM_DELETE_WINDOW',self.close_clicked)
        shell=ttk.Frame(self);shell.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(shell,highlightthickness=0)
        vertical=ttk.Scrollbar(shell,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vertical.set)
        self.canvas.pack(side='left',fill='both',expand=True);vertical.pack(side='right',fill='y')
        self.body=ttk.Frame(self.canvas,padding=12)
        self.body_window=self.canvas.create_window(0,0,anchor='nw',window=self.body)
        self.canvas.bind('<Configure>',self._canvas_resize)
        self.body.columnconfigure(0,weight=1);self.body.rowconfigure(8,weight=1)
        self.explanation=self._label('如果添加背包时提示“背包装备未定义”，请选择 w3n 战役或 w3x 地图补齐背包、装备和相关天赋定义。',
                                     'If adding a backpack reports missing definitions, choose a .w3n campaign or .w3x map to add backpack, equipment and related talent definitions.',0)
        row=ttk.Frame(self.body);row.grid(row=1,column=0,sticky='ew',pady=(10,3))
        self._text(ttk.Label(row),'战役／地图完整路径','Full campaign / map path').pack(side='left')
        self.browse=self._text(ttk.Button(row,command=self.choose_file),'选择文件…','Choose file…');self.browse.pack(side='right')
        self.input=self._path_box(2,3,editable=True)
        row=ttk.Frame(self.body);row.grid(row=3,column=0,sticky='ew',pady=(8,3))
        self._text(ttk.Label(row),'输出文件夹','Output folder').pack(side='left')
        self.choose_output=self._text(ttk.Button(row,command=self.choose_folder),'更换文件夹…','Change folder…');self.choose_output.pack(side='right')
        self.folder=self._path_box(4,2,editable=True)
        default=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'War3Trainer'/'处理结果'
        self._set(self.folder,str(default))
        controls=ttk.Frame(self.body);controls.grid(row=5,column=0,sticky='ew',pady=(10,4))
        self.process=self._text(ttk.Button(controls,command=self.process_clicked),'生成补齐后的副本','Create repaired copy');self.process.pack(side='left')
        self.stop=self._text(ttk.Button(controls,command=self.cancel.set),'停止处理','Stop');self.stop.pack(side='left',padx=8);self.stop.state(['disabled'])
        self.status=self._label('','',6)
        self.output_title=self._label('输出文件完整路径（可选中复制）','Complete output path (selectable and copyable)',7)
        self.output=self._path_box(8,5)
        bottom=ttk.Frame(self.body);bottom.grid(row=9,column=0,sticky='ew',pady=(8,3))
        self.copy=self._text(ttk.Button(bottom,command=self.copy_path),'复制输出路径','Copy output path');self.copy.pack(side='left')
        self.open=self._text(ttk.Button(bottom,command=self.open_folder),'打开输出文件夹','Open output folder');self.open.pack(side='left',padx=8)
        self.copy.state(['disabled']);self.open.state(['disabled'])
        self.notice=self._label('生成后，请把副本放入游戏相应的战役或地图目录，用魔兽 3.0 重新进入。旧存档沿用原来的地图数据。',
                               'Put the new copy in the appropriate game campaign or map folder and enter it afresh in Warcraft III 3.0. Existing saves retain the original map data.',10)
        self.body.bind('<Configure>',self._content_resize)
        self.refresh_language();self.after(100,self.poll)

    def _text(self,widget,zh,en):
        self._texts.append((widget,zh,en));return widget

    def _label(self,zh,en,row):
        widget=self._text(ttk.Label(self.body,justify='left',wraplength=730),zh,en)
        widget.grid(row=row,column=0,sticky='ew',pady=(4,2));return widget

    def _path_box(self,row,height,editable=False):
        frame=ttk.Frame(self.body);frame.grid(row=row,column=0,sticky='nsew')
        frame.columnconfigure(0,weight=1);frame.rowconfigure(0,weight=1)
        text=tk.Text(frame,height=height,width=1,wrap='char',undo=editable,relief='solid',borderwidth=1)
        text.grid(row=0,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(frame,orient='vertical',command=text.yview);scroll.grid(row=0,column=1,sticky='ns')
        text.configure(yscrollcommand=scroll.set)
        if not editable:text.configure(state='disabled')
        text.bind('<Control-a>',lambda event:self._select_all(text))
        return text

    @staticmethod
    def _select_all(text):
        text.tag_add('sel','1.0','end-1c');return 'break'

    @staticmethod
    def _set(text,value):
        state=text.cget('state');text.configure(state='normal')
        text.delete('1.0','end');text.insert('1.0',value);text.configure(state=state)

    def _wrap(self,event=None):
        width=max(100,self.body.winfo_width()-28)
        for widget,_,_ in self._texts:
            if isinstance(widget,ttk.Label):widget.configure(wraplength=width)

    def _canvas_resize(self,event=None):
        self.canvas.itemconfigure(self.body_window,width=max(1,self.canvas.winfo_width()))
        self._wrap();self.after_idle(self._fit_content)

    def _content_resize(self,event=None):
        self._wrap();self.after_idle(self._fit_content)

    def _fit_content(self):
        if not self.winfo_exists():return
        height=max(self.canvas.winfo_height(),self.body.winfo_reqheight())
        self.canvas.itemconfigure(self.body_window,height=height)
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def refresh_language(self):
        english=self.panel.get_language()=='en'
        self.title('Add 3.0 backpack definitions' if english else '为战役／地图补齐 3.0 背包定义')
        for widget,zh,en in self._texts:widget.configure(text=en if english else zh)
        self.status.configure(text=self.status_message[1 if english else 0]);self._wrap()

    def say(self,zh,en):
        self.status_message=(zh,en);self.status.configure(text=en if self.panel.get_language()=='en' else zh)

    def choose_file(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('Warcraft III','*.w3n *.w3x *.w3m'),('All files','*.*')])
        if path:self._set(self.input,path)

    def choose_folder(self):
        path=filedialog.askdirectory(parent=self)
        if path:self._set(self.folder,path)

    def process_clicked(self):
        if self.busy or self.panel.is_closing():return
        source=self.input.get('1.0','end-1c').strip().strip('"')
        folder=self.folder.get('1.0','end-1c').strip().strip('"')
        if not source or not folder:
            self.say('请填写完整的输入文件路径和输出文件夹。','Enter the full input file path and output folder.');return
        self.busy=True;self.cancel.clear();self.result=None
        self._set(self.output,'')
        for widget in (self.browse,self.choose_output,self.process,self.copy,self.open):widget.state(['disabled'])
        self.input.configure(state='disabled');self.folder.configure(state='disabled');self.stop.state(['!disabled'])
        self.say('正在复制和检查文件，请稍候…','Copying and checking the file…')
        def worker():
            try:
                result=self.panel.services.prepare_extension_definitions(source,folder,cancel=self.cancel,
                        progress=lambda stage,data:self.events.put(('progress',(stage,data))))
                self.events.put(('result',result))
            except Exception as exc:self.events.put(('error',exc))
        try:
            if self.panel.start_thread:self.panel.start_thread(worker,'war3-extension-definitions')
            else:threading.Thread(target=worker,name='war3-extension-definitions',daemon=False).start()
        except Exception as exc:self.events.put(('error',exc))

    def poll(self):
        if self.panel.is_closing():self.cancel.set()
        while True:
            try:kind,value=self.events.get_nowait()
            except queue.Empty:break
            if kind=='progress':
                stage,data=value
                if stage=='chapter_begin':
                    self.say(f'正在处理第 {data["index"]}/{data["total"]} 个章节：{data["name"]}',
                             f'Processing chapter {data["index"]}/{data["total"]}: {data["name"]}')
                elif stage=='replace_chapter':self.say('章节校验通过，正在写入新的战役副本…','Chapters verified. Writing the new campaign copy…')
                continue
            self.busy=False;self.stop.state(['disabled'])
            for widget in (self.browse,self.choose_output,self.process):widget.state(['!disabled'])
            self.input.configure(state='normal');self.folder.configure(state='normal')
            if kind=='result':
                self.result=value;self._set(self.output,value.output)
                self.copy.state(['!disabled']);self.open.state(['!disabled'])
                self.say(f'文件校验完成：共 {value.chapter_count} 个章节，补齐 {value.changed_chapters} 个章节。完整输出路径见下方。',
                         f'File verification complete: {value.changed_chapters} of {value.chapter_count} chapters updated. The complete output path is below.')
            else:
                from war3_error_messages import format_error
                path=getattr(value,'diagnostic_log_path','')
                self._set(self.output,('处理日志：\n' if self.panel.get_language()=='zh' else 'Processing log:\n')+path if path else '')
                self.say('本次处理已停止，未输出战役副本。','Processing stopped. No campaign copy was produced.')
                if not self.panel.is_closing() and not self.close_after:
                    messagebox.showerror('错误' if self.panel.get_language()=='zh' else 'Error',
                                         format_error(value,self.panel.get_language()),parent=self)
            if self.close_after or self.panel.is_closing():self.destroy();return
        if self.winfo_exists():self.after(100,self.poll)

    def copy_path(self):
        if self.result:
            self.clipboard_clear();self.clipboard_append(self.result.output)

    def open_folder(self):
        if not self.result:return
        try:os.startfile(str(Path(self.result.output).parent))
        except OSError as exc:
            from war3_error_messages import format_error
            messagebox.showerror('错误' if self.panel.get_language()=='zh' else 'Error',
                                 format_error(exc,self.panel.get_language()),parent=self)

    def close_clicked(self):
        if self.busy:
            self.close_after=True;self.cancel.set()
            self.say('正在停止处理并清理临时文件…','Stopping and cleaning temporary files…')
        else:self.destroy()
