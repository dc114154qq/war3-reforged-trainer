"""Bounded JASS declaration-order checks; no script rewriting or game access."""
from bisect import bisect_right
import re
from war3_object_tables import DefinitionError


def check_function_order(raw):
    """Catch direct calls/references to map functions declared later.

    This is not a full compiler. Calls to engine/Blizzard functions are outside
    this check. Strings, rawcodes and comments never contribute identifiers.
    """
    if len(raw)>32*1024*1024:raise DefinitionError('章节脚本超过检查范围，已保留原文件。')
    text=raw.replace(b'\r\n',b'\n').replace(b'\r',b'\n');masked=bytearray(text);i=0
    while i<len(text):
        if text[i:i+2]==b'//':
            end=text.find(b'\n',i);end=len(text) if end<0 else end
        elif text[i] in (34,39):
            quote=text[i];end=i+1
            while end<len(text):
                if text[end]==92:end+=2;continue
                if text[end]==quote:end+=1;break
                end+=1
        else:i+=1;continue
        end=min(end,len(text))
        masked[i:end]=bytes(10 if value==10 else 32 for value in text[i:end]);i=end
    masked=bytes(masked);newlines=[m.start() for m in re.finditer(b'\n',masked)]
    line=lambda at:bisect_right(newlines,at)+1
    declarations=list(re.finditer(rb'(?m)^[ \t]*(?:constant[ \t]+)?(function|native)[ \t]+([A-Za-z_][A-Za-z_0-9]*)[ \t]+takes\b',masked))
    functions={m[2]:(m.start(),line(m.start())) for m in declarations if m[1]==b'function'}
    diagnostics=dict(scope='map_function_declaration_order',full_compiler=False,functions=len(functions),
                     native_declarations=sum(m[1]==b'native' for m in declarations),forward_calls=[])
    for match in re.finditer(rb'\b([A-Za-z_][A-Za-z_0-9]*)\s*\(|\bfunction\s+([A-Za-z_][A-Za-z_0-9]*)\b(?![ \t]+takes)',masked):
        name=match[1] or match[2]
        if name not in functions or functions[name][0]<=match.start():continue
        diagnostics['forward_calls'].append(dict(function=name.decode('ascii'),line=line(match.start()),declaration_line=functions[name][1]))
        if len(diagnostics['forward_calls'])==16:break
    if diagnostics['forward_calls']:
        first=diagnostics['forward_calls'][0]
        error=DefinitionError(f'章节脚本函数顺序有错误：第 {first["line"]} 行调用 {first["function"]}，'
            f'该函数到第 {first["declaration_line"]} 行才声明。游戏会拒绝载入此章节，原文件已保留。')
        error.script_diagnostics=diagnostics;raise error
    return diagnostics
