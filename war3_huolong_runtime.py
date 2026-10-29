"""Classic HKE menus and commands with isolated names and bag protection."""
import re
from war3_huolong_data import texts,SOURCE_SHA256
from war3_jass_parser import tokens
from war3_map_script_runtime import quoted
from war3_script_features import PROTECTED_ITEMS,PROTECTED_ABILITIES
from war3_huolong_menu import generate as generate_menu

REVISION='classic-hke125b-main-menu-v2'

def configuration(options=None):
    from war3_script_features import ScriptOptions
    options=options or ScriptOptions()
    return dict(runtime='HKE 1.25B',activation=['UP','UP','LEFT','DOWN'],mainMenu=['UP','ESC'],
        helpCommands=['-h','-c','-u'],originalDefaults=True,mainMenuPageSize=6,
        enhancements='original-main-dialog',artifact_codes=list(options.artifact_codes))

def _body(source,name,body):
    pattern=r'(?m)^(function '+re.escape(name)+r' takes[^\r\n]*\r?\n).*?^endfunction'
    changed,count=re.subn(pattern,lambda m:m[1]+body+'\nendfunction',source,flags=re.S|re.M)
    if count!=1:raise ValueError('Unexpected original HKE function: '+name)
    return changed

def generate(options,prefix,known,*,protected_items=(),protected_abilities=(),levels=None):
    original=texts();globals_code=original['g.j']+'\nboolean hke_Ready = false\ngroup hke_Clones = CreateGroup()\n'
    functions=original['f.j'].replace('\r\n','\n').replace('\r','\n')
    menu_globals,menu_functions=generate_menu(options,known)
    globals_code+='\n'+menu_globals
    functions=_body(functions,'hke_Z45Z','set hke_ExP=hke_z15\ncall ExecuteFunc("hke_ExMain")')
    hook='''set hke_ExHandled=false
set hke_ExP=hke_z15
call ExecuteFunc("hke_ExClick")
if hke_ExHandled then
set hke_z05=null
set hke_z78=null
return
endif
'''
    start=functions.index('function hke_zz4Z takes')
    end=functions.index('\nendfunction',start)
    body=functions[start:end]
    needle='call hke_Z44Z(hke_z15,hke_z05,false)'
    if body.count(needle)!=1:raise ValueError('Unexpected original HKE main handler')
    functions=functions[:start]+body.replace(needle,hook+needle,1)+functions[end:]
    # The original contains a title-dependent anti-copy timer that recursively
    # executes itself and a concealed chat takeover. Neither is a game feature.
    for name in ('hke_Z71Z','hke_Z72Z','hke_Z8zZ'):
        functions=_body(functions,name,'return')
    functions=_body(functions,'hke_Z73Z','return true')
    functions=functions.replace('call SetPlayerName(Player(12),"中立生物")','// Preserve the campaign neutral-player name.')
    functions=functions.replace('InitGameCache("WuHansen.Com")','InitGameCache("'+prefix+'HKE")')
    # Original paging swaps all six slots. Keep that feature on ordinary units;
    # native 3.0 bag owners use the existing bag instead.
    needle='set hke_z65=FirstOfGroup(hke_Z8Z[hke_z15])\nif((hke_z05==GetOwningPlayer(hke_z65))and(UnitInventorySizeBJ(hke_z65)>0))then'
    replacement='''set hke_z65=FirstOfGroup(hke_Z8Z[hke_z15])
if hke_HasBag(hke_z65) then
call DisplayTimedTextToPlayer(hke_z05,0,0,8,"此单位已有3.0背包，请使用它原来的背包；火龙额外背包未执行切换。")
set hke_z65=null
return
endif
if((hke_z05==GetOwningPlayer(hke_z65))and(UnitInventorySizeBJ(hke_z65)>0))then'''
    if functions.count(needle)!=1:raise ValueError('Unexpected original HKE bag routine')
    functions=functions.replace(needle,replacement)
    items=sorted(set(PROTECTED_ITEMS)|set(protected_items));abilities=sorted(set(PROTECTED_ABILITIES)|set(protected_abilities))
    # AInv and its six-slot derivatives are ordinary classic inventories too.
    # Ability-removal protection and actual extended-bag detection differ.
    ordinary=set(known.get('ordinary_inventory',('AInv','Apak','Aion','Aihn','Aien','Aiun')))
    bag_abilities=[code for code in abilities if code not in ordinary]
    def identity(name,codes):
        return 'function hke_'+name+' takes integer id returns boolean\n'+''.join("if id == '"+code+"' then\nreturn true\nendif\n" for code in codes)+'return false\nendfunction\n'
    helpers=identity('ProtectedItem',items)+identity('ProtectedAbility',abilities)+identity('OrdinaryInventory',sorted(ordinary))
    helpers+='''function hke_HasBag takes unit u returns boolean
local integer i=0
if UnitInventorySize(u) > 6 then
return true
endif
'''+''.join("if GetUnitAbilityLevel(u,'"+code+"') > 0 then\nreturn true\nendif\n" for code in bag_abilities)+'''loop
exitwhen i >= 6
if hke_ProtectedItem(GetItemTypeId(UnitItemInSlot(u,i))) then
return true
endif
set i=i+1
endloop
return false
endfunction
function hke_Slot takes unit u, integer slot returns item
local item it=UnitItemInSlot(u,slot)
if hke_ProtectedItem(GetItemTypeId(it)) then
set it=null
endif
return it
endfunction
function hke_SlotBJ takes unit u, integer slot returns item
return hke_Slot(u,slot-1)
endfunction
function hke_AddAbility takes unit u, integer id returns boolean
if hke_OrdinaryInventory(id) then
if hke_HasBag(u) then
return false
endif
return UnitAddAbility(u,id)
endif
if hke_ProtectedAbility(id) then
return false
endif
return UnitAddAbility(u,id)
endfunction
function hke_RemoveAbility takes unit u, integer id returns boolean
if hke_OrdinaryInventory(id) then
if hke_HasBag(u) then
return false
endif
return UnitRemoveAbility(u,id)
endif
if hke_ProtectedAbility(id) then
return false
endif
return UnitRemoveAbility(u,id)
endfunction
function hke_AddItem takes unit u, integer id returns item
if hke_ProtectedItem(id) then
return null
endif
return UnitAddItemById(u,id)
endfunction
function hke_CreateItemLoc takes integer id, location position returns item
if hke_ProtectedItem(id) then
return null
endif
return CreateItemLoc(id,position)
endfunction
function hke_TagGet takes unit u returns integer
if IsUnitInGroup(u,hke_Clones) then
return 2176
endif
return 0
endfunction
function hke_TagSet takes unit u, integer tag returns nothing
if tag == 2176 then
call GroupAddUnit(hke_Clones,u)
else
call GroupRemoveUnit(hke_Clones,u)
endif
endfunction
'''
    redirects={b'UnitItemInSlot':b'hke_Slot',b'UnitItemInSlotBJ':b'hke_SlotBJ',
        b'UnitAddAbility':b'hke_AddAbility',b'UnitRemoveAbility':b'hke_RemoveAbility',
        b'UnitAddItemById':b'hke_AddItem',b'CreateItemLoc':b'hke_CreateItemLoc',
        b'GetUnitUserData':b'hke_TagGet',b'SetUnitUserData':b'hke_TagSet'}
    raw=functions.encode('utf-8')
    for token in reversed(tokens(raw)):
        if token.kind=='identifier' and token.value in redirects:
            raw=raw[:token.start]+redirects[token.value]+raw[token.end:]
    input_prefix='!hl'+prefix[2:8].lower()
    menu_functions=menu_functions.replace('__INPUT_LEN__',str(len(input_prefix)+1)).replace('__INPUT__',input_prefix).replace('__CACHE__',prefix+'Menu')
    functions=helpers+raw.decode('utf-8')+'\n'+menu_functions+'''\nfunction hke_Boot takes nothing returns nothing
if hke_Ready then
return
endif
set hke_Ready=true
call ExecuteFunc("hke_z09Z")
call ExecuteFunc("hke_ExInit")
endfunction
'''
    def namespace(raw):
        parsed=tokens(raw)
        pieces=[];cursor=0;encoded_prefix=prefix.encode()
        for i,token in enumerate(parsed):
            replacement=None
            if token.kind=='identifier' and token.value.startswith(b'hke_'):
                replacement=encoded_prefix+token.value[4:]
            elif token.kind=='string' and i>=2 and parsed[i-2].value==b'ExecuteFunc' and token.value.startswith(b'"hke_'):
                replacement=b'"'+encoded_prefix+token.value[5:]
            if replacement is not None:
                pieces.extend((raw[cursor:token.start],replacement));cursor=token.end
        pieces.append(raw[cursor:])
        return b''.join(pieces)
    return namespace(globals_code.encode()),namespace(functions.encode())

def usage(options):
    original=texts()['f.j']
    lines=['经典版火龙修改器：HKE 1.25B 游戏内功能','',
        '本版按 HkeW3mModifier 2.06 附带的原版 HKE 1.25B 脚本加入完整菜单和命令。',
        '原作者：火龙 / WuHansen。功能写进地图副本，关闭或移走修改器仍可使用。',
        '', '进入新副本后，依次按 ↑、↑、←、↓ 激活。',
        '激活后先按 ↑ 再按 Esc（1秒内）打开主菜单；↑ 后双击单位打开单个单位菜单。',
        '输入 -h 查看键盘帮助，-c 查看命令帮助，-u 查看单位类命令帮助。',
        '主菜单包含：资源、自动化、选定单位特殊属性、个人选项、帮助、其他玩家管理、游戏作弊选项。',
        '新增功能直接位于火龙原主菜单，使用上一页／下一页翻页；没有独立的增强主菜单。',
        '新增物品／技能／单位召唤／科技目录、六神器方案、物品槽操作、批量修改、英雄成长、传送标记、资源与金矿、自动管理、收藏和执行记录。',
        '不增加镜头设置、操作目标管理或单位信息页。每页最多6个功能；目录每页4个对象，另有搜索和筛选。',
        '精确数值和搜索词按游戏内提示的专用聊天前缀输入，60秒超时取消；输入期间绑定原选择，不随新的选择漂移。',
        '生成物品只处理普通物品栏，满包不删原物品；可选择生成到地面。光环和被动逐项添加并读回地图有效等级。',
        '位置标记、收藏、最近记录和绑定自动项限当前章节；不承诺跨图继承。旧式引擎不提供冷却、缩放等完整读回，结果中会区分调用与可读回状态。',
        '六神器代码：'+', '.join(options.artifact_codes),
        '本轮适用本地单人 JASS 地图/战役；Lua 暂不支持。原地图的游戏版本要求不变。',
        '3.0 背包仍使用现有专用功能。已有3.0背包的单位会跳过火龙旧式额外背包切换；载体和控制能力受到保护。',
        '从副本章节入口进入；旧存档不会自动得到新增脚本。',
        '', '以下帮助文字直接来自原版脚本：']
    for name in ('hke_Z6zZ','hke_Z60Z','hke_Z61Z'):
        body=re.search(r'(?m)^function '+name+r' takes.*?^endfunction',original,re.S|re.M)[0]
        for text in re.findall(r'DisplayTimedTextToPlayer\([^\n]*?,"([^"\n]*)"\)',body):
            text=re.sub(r'\|[cC][0-9a-fA-F]{8}|\|[rR]','',text).replace('|n','\n')
            if not text.startswith('欢迎使用'):lines.append(text)
    lines+=['','兼容处理：隔离脚本名称；保留地图单位自定义数据；保护3.0背包；移除原版隐藏接管指令和标题校验递归计时器。',
        '当前已进行脚本编译和归档检查，未据此宣称完成游戏内逐功能实测。']
    return '\n'.join(lines)+'\n'
