"""Generate a self-contained classic-JASS runtime: no host, files or DLL calls."""
import json
from war3_script_features import PROTECTED_ABILITIES, PROTECTED_ITEMS

REVISION = 'map-tools-jass-v1'
ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz'
PRESETS = {
    'auras': ('AHab','AHad','AEar','AEah','AOac','AOae','AUau','AUav','Aakb'),
    'passives': ('AOcr','AOev','AHbh','ANca','ANba','AUts','AEev'),
}
MENUS = {
    'resources': ('资源与金矿', [('加金币','gold {amount}'),('加木材','lumber {amount}'),('人口上限 100','foodcap 100'),('金币维持 {amount}','goldlock {amount}'),('木材维持 {amount}','lumberlock {amount}'),('金矿金额 {amount}','mine {amount}')]),
    'hero': ('英雄', [('英雄等级 10','level 10'),('三围各 100','stats 100'),('技能点 +1','points 1'),('复活','revive'),('经验倍率 2','xprate 2')]),
    'units': ('单位', [('恢复生命','heal'),('恢复魔法','mana'),('开启无敌','invuln'),('关闭无敌','vulnerable'),('穿墙','ghost'),('恢复碰撞','solid'),('暂停单位','pause'),('恢复行动','resume'),('基础复制','clone')]),
    'abilities': ('技能', [('添加常用光环','auras'),('添加常用被动','passives'),('清除冷却','cooldown')]),
    'items': ('物品', [('领取六神器方案','artifacts')]),
    'automatic': ('自动功能', [('当前选择自动回血','autoheal on'),('停止自动回血','autoheal off'),('当前选择自动回魔','automana on'),('停止自动回魔','automana off'),('当前选择自动清冷却','autocd on'),('停止自动清冷却','autocd off'),('停止全部自动项与资源维持','stop')]),
    'world': ('游戏设置', [('显示地图','reveal'),('恢复地图迷雾','fog'),('时间设为正午','time 12'),('时间设为午夜','time 0')]),
}
HELP = {
    'resources': 'gold 数量 / goldset 数量 / lumber 数量 / lumberset 数量 / foodcap 数量 / foodused 数量 / mine 数量 / goldlock 最低值 / lumberlock 最低值（0 停止维持）',
    'hero': 'level 等级 / xp 经验 / str 数值 / agi 数值 / int 数值 / stats 数值 / points 增量 / xprate 倍率 / revive',
    'units': 'heal / mana / hp 生命 / mp 魔法 / invuln / vulnerable / ghost / solid / pause / resume / scale 比例 / owner 玩家号(1-12) / unit 单位代码 / move X Y / clone（仅基础状态，不复制物品、附加技能和扩展状态）',
    'abilities': 'ability 技能代码 等级 / unability 技能代码 / abilitylevel 技能代码 等级 / auras / passives / cooldown；背包控制能力禁止删除或改级',
    'items': 'item 物品代码 [充能] / charges 槽位(1-6) 数量 / artifacts；满包先跳过，不删除原物品',
    'automatic': 'autoheal on|off / automana on|off / autocd on|off：每项绑定执行时所选最多32个单位。stop：停止本玩家全部自动项和资源维持',
    'world': 'reveal / fog / time 小时(0-24) / tech 科技代码 等级',
}


def quoted(text):
    return json.dumps(str(text), ensure_ascii=False)


def generate(options, prefix, known, *, protected_items=(), protected_abilities=(), levels=None):
    """Return globals/functions. All identifiers are allocated from a scanned prefix."""
    levels = levels or {}
    protected_items = set(PROTECTED_ITEMS) | set(protected_items)
    protected_abilities = set(PROTECTED_ABILITIES) | set(protected_abilities)
    globals_code = '''
boolean MX_ready = false
dialog array MX_dialogs
button array MX_buttons
string array MX_actions
integer array MX_pages
group array MX_auto
integer array MX_gold
integer array MX_lumber
integer MX_active = 0
integer MX_cursor = 0
timer MX_clock = null
fogmodifier array MX_vision
string array MX_ids0
string array MX_ids1
string array MX_ids2
string array MX_ids3
integer array MX_counts
unit MX_target = null
player MX_player = null
string MX_command = ""
string MX_argument = ""
real MX_value = 0
real MX_second = 0
boolean MX_result = false
'''
    for feature in MENUS:
        globals_code += f'boolean MX_{feature} = '+('true' if feature in options.features else 'false')+'\n'

    functions = r'''
function MX_Min takes real a, real b returns real
    if a < b then
        return a
    endif
    return b
endfunction

function MX_Max takes real a, real b returns real
    if a > b then
        return a
    endif
    return b
endfunction

function MX_Mod takes integer a, integer b returns integer
    return a-(a/b)*b
endfunction

function MX_Say takes player p, string s returns nothing
    call DisplayTimedTextToPlayer(p, 0, 0, 15, "|cffffcc66[地图功能]|r "+s)
endfunction

function MX_Arg takes string s, integer wanted returns string
    local integer i = 0
    local integer start = 0
    local integer n = 0
    local integer length = StringLength(s)
    loop
        exitwhen i >= length
        if SubString(s,i,i+1) != " " then
            set start = i
            loop
                exitwhen i >= length or SubString(s,i,i+1) == " "
                set i = i+1
            endloop
            if n == wanted then
                return SubString(s,start,i)
            endif
            set n = n+1
        else
            set i = i+1
        endif
    endloop
    return ""
endfunction

function MX_Number takes string s returns boolean
    local integer i = 0
    local integer j = 0
    local integer digits = 0
    local integer dots = 0
    local string c
    if StringLength(s) == 0 or StringLength(s) > 12 then
        return false
    endif
    if SubString(s,0,1) == "-" then
        set i = 1
    endif
    loop
        exitwhen i >= StringLength(s)
        set c = SubString(s,i,i+1)
        if c == "." then
            set dots = dots+1
            if dots > 1 then
                return false
            endif
        else
            set j = 0
            loop
                exitwhen j == 10 or SubString("0123456789",j,j+1) == c
                set j = j+1
            endloop
            if j == 10 then
                return false
            endif
            set digits = digits+1
        endif
        set i = i+1
    endloop
    return digits > 0
endfunction

function MX_Code takes string s returns integer
    local string chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"
    local string c
    local integer i = 0
    local integer j
    local integer ascii
    local integer result = 0
    if StringLength(s) != 4 then
        return 0
    endif
    loop
        exitwhen i == 4
        set c = SubString(s,i,i+1)
        set j = 0
        loop
            exitwhen j == 63 or SubString(chars,j,j+1) == c
            set j = j+1
        endloop
        if j == 63 then
            return 0
        elseif j < 10 then
            set ascii = j+48
        elseif j < 36 then
            set ascii = j+55
        elseif j == 36 then
            set ascii = 95
        else
            set ascii = j+60
        endif
        set result = result*256+ascii
        set i = i+1
    endloop
    return result
endfunction

function MX_Integer takes string s returns boolean
    local integer i = 0
    local string c
    if StringLength(s) == 0 or StringLength(s) > 9 then
        return false
    endif
    loop
        exitwhen i == StringLength(s)
        set c = SubString(s,i,i+1)
        if c == "." or c == "-" then
            return false
        endif
        set i = i+1
    endloop
    return MX_Number(s) and S2I(s) <= 100000000
endfunction

function MX_Known takes integer kind, integer code returns boolean
    local integer lo = 0
    local integer hi = MX_counts[kind]-1
    local integer mid
    local integer pos
    local integer found
    local string chunk
    if code == 0 then
        return false
    endif
    loop
        exitwhen lo > hi
        set mid = (lo+hi)/2
        set pos = ModuloInteger(mid,100)*4
        if kind == 0 then
            set chunk = MX_ids0[mid/100]
        elseif kind == 1 then
            set chunk = MX_ids1[mid/100]
        elseif kind == 2 then
            set chunk = MX_ids2[mid/100]
        else
            set chunk = MX_ids3[mid/100]
        endif
        set found = MX_Code(SubString(chunk,pos,pos+4))
        if found == code then
            return true
        elseif found < code then
            set lo = mid+1
        else
            set hi = mid-1
        endif
    endloop
    return false
endfunction
'''
    for name, values in [('ProtectedItem', protected_items), ('ProtectedAbility', protected_abilities)]:
        codes = sorted(c for c in values if len(c) == 4 and all(x in ALPHABET for x in c))
        functions += f'\nfunction MX_{name} takes integer code returns boolean\n    return '+' or '.join("code == '"+c+"'" for c in codes)+'\nendfunction\n'
    functions += r'''
function MX_AddItem takes unit u, integer code, integer charges, player p returns boolean
    local integer slot = 0
    local integer size = UnitInventorySize(u)
    local item it = null
    local boolean free = false
    if size > 6 then
        set size = 6
    endif
    if not MX_Known(0,code) or MX_ProtectedItem(code) or UnitInventorySize(u) <= 0 then
        return false
    endif
    loop
        exitwhen slot >= size
        if UnitItemInSlot(u,slot) == null then
            set free = true
        endif
        set slot = slot+1
    endloop
    if not free then
        return false
    endif
    set it = CreateItem(code,GetUnitX(u),GetUnitY(u))
    if it == null then
        return false
    endif
    if charges > 0 then
        call SetItemCharges(it,charges)
    endif
    if not UnitAddItem(u,it) then
        call MX_Say(p,"新物品未确认入栏，已保留在原地或地图接管的位置，请自行查看；原物品未删除。")
        set it = null
        return false
    endif
    set it = null
    return true
endfunction

function MX_Copy takes unit u, player p returns boolean
    local unit copy = null
    local real x = GetUnitX(u)+64
    local real y = GetUnitY(u)+64
    local rect bounds = GetWorldBounds()
    if x > GetRectMaxX(bounds)-64 then
        set x = GetUnitX(u)-64
    endif
    if y > GetRectMaxY(bounds)-64 then
        set y = GetUnitY(u)-64
    endif
    call RemoveRect(bounds)
    set bounds = null
    if not MX_Known(1,GetUnitTypeId(u)) then
        return false
    endif
    set copy = CreateUnit(GetOwningPlayer(u),GetUnitTypeId(u),x,y,GetUnitFacing(u))
    if copy == null then
        return false
    endif
    if IsUnitType(u,UNIT_TYPE_HERO) then
        call SetHeroLevel(copy,GetHeroLevel(u),false)
        call SetHeroStr(copy,GetHeroStr(u,false),true)
        call SetHeroAgi(copy,GetHeroAgi(u,false),true)
        call SetHeroInt(copy,GetHeroInt(u,false),true)
    endif
    call SetUnitState(copy,UNIT_STATE_LIFE,GetUnitState(copy,UNIT_STATE_MAX_LIFE)*GetUnitState(u,UNIT_STATE_LIFE)/RMaxBJ(1,GetUnitState(u,UNIT_STATE_MAX_LIFE)))
    call SetUnitState(copy,UNIT_STATE_MANA,GetUnitState(copy,UNIT_STATE_MAX_MANA)*GetUnitState(u,UNIT_STATE_MANA)/RMaxBJ(1,GetUnitState(u,UNIT_STATE_MAX_MANA)))
    set copy = null
    return true
endfunction
'''
    for preset, codes in PRESETS.items():
        functions += f'\nfunction MX_{preset} takes unit u returns boolean\n    local integer changed = 0\n'
        for code in codes:
            maximum = min(100, max(1, int(levels.get(code, 3))))
            functions += f'''    if MX_Known(2,'{code}') then
        if GetUnitAbilityLevel(u,'{code}') == 0 then
            call UnitAddAbility(u,'{code}')
        endif
        if GetUnitAbilityLevel(u,'{code}') > 0 then
            call SetUnitAbilityLevel(u,'{code}',{maximum})
            set changed = changed+1
        endif
    endif
'''
        functions += '    return changed > 0\nendfunction\n'

    functions += r'''
function MX_Unit takes unit u, player p, string c, real v, string arg, real second returns boolean
    local integer code = MX_Code(arg)
    local item it = null
    local boolean changed = false
    if u == null or GetUnitTypeId(u) == 0 then
        return false
    endif
    if c == "level" then
        if not IsUnitType(u,UNIT_TYPE_HERO) then
            return false
        endif
        call SetHeroLevel(u,S2I(arg),false)
        return GetHeroLevel(u) == S2I(arg)
    elseif c == "xp" then
        if not IsUnitType(u,UNIT_TYPE_HERO) then
            return false
        endif
        call SetHeroXP(u,S2I(arg),false)
    elseif c == "str" or c == "agi" or c == "int" or c == "stats" then
        if not IsUnitType(u,UNIT_TYPE_HERO) then
            return false
        endif
        if c == "str" or c == "stats" then
            call SetHeroStr(u,S2I(arg),true)
        endif
        if c == "agi" or c == "stats" then
            call SetHeroAgi(u,S2I(arg),true)
        endif
        if c == "int" or c == "stats" then
            call SetHeroInt(u,S2I(arg),true)
        endif
    elseif c == "points" then
        if not IsUnitType(u,UNIT_TYPE_HERO) then
            return false
        endif
        return UnitModifySkillPoints(u,S2I(arg))
    elseif c == "revive" then
        if not IsUnitType(u,UNIT_TYPE_HERO) or GetUnitState(u,UNIT_STATE_LIFE) > .405 then
            return false
        endif
        return ReviveHero(u,GetUnitX(u),GetUnitY(u),false)
    elseif c == "heal" then
        if GetUnitState(u,UNIT_STATE_LIFE) <= .405 then
            return false
        endif
        call SetUnitState(u,UNIT_STATE_LIFE,GetUnitState(u,UNIT_STATE_MAX_LIFE))
    elseif c == "mana" then
        call SetUnitState(u,UNIT_STATE_MANA,GetUnitState(u,UNIT_STATE_MAX_MANA))
    elseif c == "hp" then
        call SetUnitState(u,UNIT_STATE_LIFE,v)
    elseif c == "mp" then
        call SetUnitState(u,UNIT_STATE_MANA,v)
    elseif c == "invuln" or c == "vulnerable" then
        call SetUnitInvulnerable(u,c == "invuln")
    elseif c == "ghost" or c == "solid" then
        call SetUnitPathing(u,c == "solid")
    elseif c == "pause" or c == "resume" then
        call PauseUnit(u,c == "pause")
    elseif c == "scale" then
        call SetUnitScale(u,v,v,v)
    elseif c == "owner" then
        call SetUnitOwner(u,Player(S2I(arg)-1),true)
    elseif c == "move" then
        call SetUnitPosition(u,v,second)
    elseif c == "mine" then
        if GetResourceAmount(u) <= 0 then
            return false
        endif
        call SetResourceAmount(u,S2I(arg))
        return GetResourceAmount(u) == S2I(arg)
    elseif c == "cooldown" then
        call UnitResetCooldown(u)
    elseif c == "ability" or c == "abilitylevel" then
        if not MX_Known(2,code) or MX_ProtectedAbility(code) then
            return false
        endif
        if c == "ability" and GetUnitAbilityLevel(u,code) == 0 then
            call UnitAddAbility(u,code)
        endif
        if GetUnitAbilityLevel(u,code) == 0 then
            return false
        endif
        call SetUnitAbilityLevel(u,code,R2I(second))
        return GetUnitAbilityLevel(u,code) == R2I(second)
    elseif c == "unability" then
        if MX_ProtectedAbility(code) or not MX_Known(2,code) then
            return false
        endif
        if GetUnitAbilityLevel(u,code) == 0 then
            return false
        endif
        call UnitRemoveAbility(u,code)
        return GetUnitAbilityLevel(u,code) == 0
    elseif c == "auras" then
        return MX_auras(u)
    elseif c == "passives" then
        return MX_passives(u)
    elseif c == "item" then
        return MX_AddItem(u,code,R2I(second),p)
    elseif c == "charges" then
        set it = UnitItemInSlot(u,R2I(v)-1)
        if it == null or MX_ProtectedItem(GetItemTypeId(it)) then
            set it = null
            return false
        endif
        call SetItemCharges(it,R2I(second))
        set changed = GetItemCharges(it) == R2I(second)
        set it = null
        return changed
    elseif c == "artifacts" then
ARTIFACT_BODY
        return changed
    elseif c == "clone" then
        return MX_Copy(u,p)
    endif
    return true
endfunction

function MX_ApplyTarget takes nothing returns nothing
    set MX_result = MX_Unit(MX_target,MX_player,MX_command,MX_value,MX_argument,MX_second)
endfunction

function MX_DeadHero takes nothing returns boolean
    return IsUnitType(GetFilterUnit(),UNIT_TYPE_HERO) and GetUnitState(GetFilterUnit(),UNIT_STATE_LIFE) <= .405
endfunction

function MX_Run takes player p, string c, real v, string arg, real second returns nothing
    local group g = CreateGroup()
    local unit u = null
    local integer seen = 0
    local integer done = 0
    local boolexpr filter = null
    call GroupEnumUnitsSelected(g,p,null)
    if c == "revive" and FirstOfGroup(g) == null then
        set filter = Condition(function MX_DeadHero)
        call GroupEnumUnitsOfPlayer(g,p,filter)
        call DestroyBoolExpr(filter)
        set filter = null
    endif
    loop
        set u = FirstOfGroup(g)
        exitwhen u == null or seen == 32
        call GroupRemoveUnit(g,u)
        set seen = seen+1
        set MX_target = u
        set MX_player = p
        set MX_command = c
        set MX_argument = arg
        set MX_value = v
        set MX_second = second
        set MX_result = false
        call ExecuteFunc("MX_ApplyTarget")
        if MX_result then
            set done = done+1
        endif
        set MX_target = null
        set MX_player = null
    endloop
    call DestroyGroup(g)
    call MX_Say(p,"已处理 "+I2S(done)+" 个目标；跳过或未确认 "+I2S(seen-done)+" 个。每次最多32个目标。")
    if seen == 0 then
        call MX_Say(p,"请先选择要操作的单位。")
    endif
    set g = null
    set u = null
endfunction

function MX_Tick takes nothing returns nothing
    local integer id = MX_cursor
    local integer kind = 0
    local integer seen = 0
    local group g = null
    local group keep = null
    local unit u = null
    local player p = Player(id)
    set MX_cursor = ModuloInteger(id+1,12)
    if MX_gold[id] > 0 and GetPlayerState(p,PLAYER_STATE_RESOURCE_GOLD) < MX_gold[id] then
        call SetPlayerState(p,PLAYER_STATE_RESOURCE_GOLD,MX_gold[id])
    endif
    if MX_lumber[id] > 0 and GetPlayerState(p,PLAYER_STATE_RESOURCE_LUMBER) < MX_lumber[id] then
        call SetPlayerState(p,PLAYER_STATE_RESOURCE_LUMBER,MX_lumber[id])
    endif
    loop
        exitwhen kind == 3
        set g = MX_auto[id*3+kind]
        if g != null then
            set keep = CreateGroup()
            set seen = 0
            loop
                set u = FirstOfGroup(g)
                exitwhen u == null or seen == 32
                call GroupRemoveUnit(g,u)
                set seen = seen+1
                if GetUnitTypeId(u) != 0 then
                    call GroupAddUnit(keep,u)
                    if GetUnitState(u,UNIT_STATE_LIFE) > .405 then
                        if kind == 0 then
                            call SetUnitState(u,UNIT_STATE_LIFE,GetUnitState(u,UNIT_STATE_MAX_LIFE))
                        elseif kind == 1 then
                            call SetUnitState(u,UNIT_STATE_MANA,GetUnitState(u,UNIT_STATE_MAX_MANA))
                        else
                            call UnitResetCooldown(u)
                        endif
                    endif
                endif
            endloop
            call DestroyGroup(g)
            if FirstOfGroup(keep) == null then
                call DestroyGroup(keep)
                set keep = null
                set MX_active = MX_active-1
            endif
            set MX_auto[id*3+kind] = keep
        endif
        set kind = kind+1
    endloop
    if MX_active == 0 then
        call PauseTimer(MX_clock)
    endif
    set g = null
    set keep = null
    set u = null
    set p = null
endfunction

function MX_Auto takes player p, integer kind, boolean enabled returns nothing
    local integer id = GetPlayerId(p)*3+kind
    local group source = null
    local unit u = null
    local integer count = 0
    if MX_auto[id] != null then
        call DestroyGroup(MX_auto[id])
        set MX_auto[id] = null
        set MX_active = MX_active-1
    endif
    if enabled then
        set source = CreateGroup()
        set MX_auto[id] = CreateGroup()
        call GroupEnumUnitsSelected(source,p,null)
        loop
            set u = FirstOfGroup(source)
            exitwhen u == null or count == 32
            call GroupRemoveUnit(source,u)
            call GroupAddUnit(MX_auto[id],u)
            set count = count+1
        endloop
        call DestroyGroup(source)
        if count == 0 then
            call DestroyGroup(MX_auto[id])
            set MX_auto[id] = null
        else
            set MX_active = MX_active+1
            call TimerStart(MX_clock,.1,true,function MX_Tick)
        endif
    endif
    call MX_Say(p,"自动项已更新；本项绑定 "+I2S(count)+" 个目标。每个玩家约1.2秒处理一轮。")
    set source = null
    set u = null
endfunction
'''
    artifacts = ''
    for code in options.artifact_codes:
        artifacts += f"        if MX_AddItem(u,'{code}',0,p) then\n            set changed = true\n        endif\n"
    functions = functions.replace('ARTIFACT_BODY', artifacts.rstrip())

    # Menus and documentation are embedded: no quest-data edits or external lookup.
    functions += '\nfunction MX_Help takes player p, string page returns nothing\n'
    functions += '    call MX_Say(p,'+quoted('输入 '+options.prefix+' 打开菜单；命令格式：'+options.prefix+' 命令 参数。代码区分大小写。操作当前所选，最多32个；支持前12个玩家槽位。')+')\n'
    for cat in options.features:
        functions += f'    if page == "" or page == "{cat}" then\n        call MX_Say(p,{quoted(HELP[cat])})\n    endif\n'
    functions += 'endfunction\n'
    functions += '''
function MX_Button takes integer pid, integer slot, string label, string action returns nothing
    set MX_buttons[pid*12+slot] = DialogAddButton(MX_dialogs[pid],label,0)
    set MX_actions[pid*12+slot] = action
endfunction

function MX_Menu takes player p, integer page returns nothing
    local integer pid = GetPlayerId(p)
    local integer i = 0
    call DialogClear(MX_dialogs[pid])
    loop
        exitwhen i == 12
        set MX_buttons[pid*12+i] = null
        set MX_actions[pid*12+i] = ""
        set i = i+1
    endloop
    set MX_pages[pid] = page
    call DialogSetMessage(MX_dialogs[pid],"地图功能 - 选择操作")
    if page == 0 then
'''
    for index, cat in enumerate(options.features, 1):
        functions += f'        call MX_Button(pid,{index-1},{quoted(MENUS[cat][0])},{quoted("menu "+str(index))})\n'
    functions += f'        call MX_Button(pid,{len(options.features)},"命令帮助","help")\n'
    for index, cat in enumerate(options.features, 1):
        functions += f'    elseif page == {index} then\n'
        for slot, (label, command) in enumerate(MENUS[cat][1]):
            label = label.format(amount=options.resource_amount)
            command = command.format(amount=options.resource_amount)
            functions += f'        call MX_Button(pid,{slot},{quoted(label)},{quoted(command)})\n'
        functions += f'        call MX_Button(pid,9,"本页命令说明",{quoted("help "+cat)})\n        call MX_Button(pid,10,"返回主菜单","menu 0")\n'
    functions += '''    endif
    call MX_Button(pid,11,"关闭菜单","")
    call DialogDisplay(p,MX_dialogs[pid],true)
endfunction
'''
    command_groups = {
        'resources': 'gold goldset lumber lumberset foodcap foodused mine goldlock lumberlock',
        'hero': 'level xp str agi int stats points revive xprate',
        'units': 'heal mana hp mp invuln vulnerable ghost solid pause resume scale owner unit move clone',
        'abilities': 'ability unability abilitylevel auras passives cooldown',
        'items': 'item charges artifacts', 'automatic': 'autoheal automana autocd stop',
        'world': 'reveal fog time tech',
    }
    functions += '\nfunction MX_Allowed takes string c returns boolean\n'
    for cat, commands in command_groups.items():
        functions += '    if '+' or '.join('c == '+quoted(c) for c in commands.split())+f' then\n        return MX_{cat}\n    endif\n'
    functions += '    return false\nendfunction\n'
    functions += r'''
function MX_Dispatch takes player p, string text returns nothing
    local string c = StringCase(MX_Arg(text,0),false)
    local string a = MX_Arg(text,1)
    local string b = MX_Arg(text,2)
    local real v = S2R(a)
    local real second = S2R(b)
    local integer id = GetPlayerId(p)
    local integer kind = 0
    local integer i = 0
    local integer amount = S2I(a)
    local integer current = 0
    local unit u = null
    local group g = null
    local rect bounds = null
    if StringLength(text) > 128 or MX_Arg(text,3) != "" or id < 0 or id > 11 then
        return
    endif
    if c == "" or c == "menu" then
        if a == "" then
            call MX_Menu(p,0)
        elseif MX_Number(a) and v == I2R(R2I(v)) and v >= 0 and v <= MENU_COUNT then
            call MX_Menu(p,R2I(v))
        endif
        return
    elseif c == "help" then
        call MX_Help(p,a)
        return
    elseif not MX_Allowed(c) then
        call MX_Say(p,"本次副本没有这个命令。输入 PREFIX help 查看已加入的功能。")
        return
    endif
    if c == "autoheal" or c == "automana" or c == "autocd" then
        if a != "on" and a != "off" then
            call MX_Say(p,"请填写 on 或 off。")
            return
        endif
        if c == "automana" then
            set kind = 1
        elseif c == "autocd" then
            set kind = 2
        endif
        call MX_Auto(p,kind,a == "on")
        return
    elseif c == "stop" then
        loop
            exitwhen i == 3
            call MX_Auto(p,i,false)
            set i = i+1
        endloop
        if MX_gold[id] > 0 then
            set MX_active = MX_active-1
        endif
        if MX_lumber[id] > 0 then
            set MX_active = MX_active-1
        endif
        set MX_gold[id] = 0
        set MX_lumber[id] = 0
        call MX_Say(p,"已停止本玩家的全部自动项和资源维持。")
        return
    endif
    if c == "item" or c == "ability" or c == "abilitylevel" or c == "unability" or c == "unit" or c == "tech" then
        if MX_Code(a) == 0 then
            call MX_Say(p,"请填写4位物品、技能、单位或科技代码，区分大小写。")
            return
        endif
        if c == "ability" or c == "abilitylevel" then
            if not MX_Integer(b) or second < 1 or second > 100 then
                call MX_Say(p,"技能等级应为1到100的整数。")
                return
            endif
        elseif c == "item" then
            if b != "" and (not MX_Integer(b) or second < 1 or second > 10000) then
                call MX_Say(p,"充能应为1到10000的整数，也可以省略。")
                return
            endif
        elseif c == "tech" then
            if not MX_Integer(b) or second < 0 or second > 100 then
                call MX_Say(p,"科技等级应为0到100的整数。")
                return
            endif
        endif
    elseif c == "charges" then
        if not MX_Integer(a) or not MX_Integer(b) or v < 1 or v > 6 or second < 0 or second > 10000 then
            call MX_Say(p,"格式：charges 槽位(1-6) 数量(0-10000)。")
            return
        endif
    elseif c == "move" then
        if not MX_Number(a) or not MX_Number(b) then
            call MX_Say(p,"格式：move X Y；会使用游戏的可放置位置。")
            return
        endif
        set bounds = GetWorldBounds()
        if v < GetRectMinX(bounds)+64 or v > GetRectMaxX(bounds)-64 or second < GetRectMinY(bounds)+64 or second > GetRectMaxY(bounds)-64 then
            call RemoveRect(bounds)
            set bounds = null
            call MX_Say(p,"坐标超出地图范围。")
            return
        endif
        call RemoveRect(bounds)
        set bounds = null
    elseif c == "gold" or c == "goldset" or c == "lumber" or c == "lumberset" or c == "goldlock" or c == "lumberlock" or c == "foodcap" or c == "foodused" or c == "level" or c == "xp" or c == "str" or c == "agi" or c == "int" or c == "stats" or c == "points" or c == "hp" or c == "mp" or c == "mine" or c == "owner" or c == "scale" or c == "xprate" or c == "time" then
        if not MX_Number(a) or v < 0 or v > 100000000 then
            call MX_Say(p,"数值必须在0到100000000之间。")
            return
        endif
        if c != "scale" and c != "xprate" and c != "time" and not MX_Integer(a) then
            call MX_Say(p,"这个命令需要整数。")
            return
        endif
        if (c == "scale" and (v < .05 or v > 10)) or (c == "xprate" and v > 10) or (c == "time" and v > 24) or (c == "level" and (v < 1 or v > 10000)) or (c == "owner" and (v < 1 or v > 12)) or ((c == "foodcap" or c == "foodused") and v > 300) or (c == "points" and (v < 1 or v > 10000)) then
            call MX_Say(p,"数值超出本功能支持的范围，请输入 PREFIX help 查看说明。")
            return
        endif
        if b != "" then
            call MX_Say(p,"这个命令只接受一个数值。")
            return
        endif
    elseif a != "" or b != "" then
        call MX_Say(p,"这个命令不需要参数。")
        return
    endif
    if c == "gold" or c == "goldset" then
        if c == "gold" then
            set current = GetPlayerState(p,PLAYER_STATE_RESOURCE_GOLD)
            if current > 1000000000-amount then
                call MX_Say(p,"金币超过本功能支持的范围，已保留原值。")
                return
            endif
            set amount = current+amount
        endif
        call SetPlayerState(p,PLAYER_STATE_RESOURCE_GOLD,amount)
    elseif c == "lumber" or c == "lumberset" then
        if c == "lumber" then
            set current = GetPlayerState(p,PLAYER_STATE_RESOURCE_LUMBER)
            if current > 1000000000-amount then
                call MX_Say(p,"木材超过本功能支持的范围，已保留原值。")
                return
            endif
            set amount = current+amount
        endif
        call SetPlayerState(p,PLAYER_STATE_RESOURCE_LUMBER,amount)
    elseif c == "foodcap" then
        call SetPlayerState(p,PLAYER_STATE_FOOD_CAP_CEILING,amount)
        call SetPlayerState(p,PLAYER_STATE_RESOURCE_FOOD_CAP,amount)
    elseif c == "foodused" then
        call SetPlayerState(p,PLAYER_STATE_RESOURCE_FOOD_USED,amount)
    elseif c == "goldlock" or c == "lumberlock" then
        if c == "goldlock" then
            if MX_gold[id] > 0 then
                set MX_active = MX_active-1
            endif
            set MX_gold[id] = amount
        else
            if MX_lumber[id] > 0 then
                set MX_active = MX_active-1
            endif
            set MX_lumber[id] = amount
        endif
        if v > 0 then
            set MX_active = MX_active+1
            call TimerStart(MX_clock,.1,true,function MX_Tick)
        endif
    elseif c == "xprate" then
        call SetPlayerHandicapXP(p,v)
    elseif c == "time" then
        call SetFloatGameState(GAME_STATE_TIME_OF_DAY,v)
    elseif c == "tech" then
        if not MX_Known(3,MX_Code(a)) or GetPlayerTechMaxAllowed(p,MX_Code(a)) == 0 or (GetPlayerTechMaxAllowed(p,MX_Code(a)) > 0 and R2I(second) > GetPlayerTechMaxAllowed(p,MX_Code(a))) then
            call MX_Say(p,"科技没有开放或等级超过当前地图允许的上限，已跳过。")
            return
        endif
        call SetPlayerTechResearched(p,MX_Code(a),R2I(second))
        if GetPlayerTechCount(p,MX_Code(a),true) != R2I(second) then
            call MX_Say(p,"科技等级未按要求读回，请以地图状态为准。")
            return
        endif
    elseif c == "reveal" then
        if MX_vision[id] == null then
            set bounds = GetWorldBounds()
            set MX_vision[id] = CreateFogModifierRect(p,FOG_OF_WAR_VISIBLE,bounds,false,false)
            call RemoveRect(bounds)
            set bounds = null
        endif
        call FogModifierStart(MX_vision[id])
    elseif c == "fog" then
        if MX_vision[id] != null then
            call FogModifierStop(MX_vision[id])
            call DestroyFogModifier(MX_vision[id])
            set MX_vision[id] = null
        endif
    elseif c == "unit" then
        if not MX_Known(1,MX_Code(a)) then
            call MX_Say(p,"当前地图目录中没有这个单位定义。")
            return
        endif
        set g = CreateGroup()
        call GroupEnumUnitsSelected(g,p,null)
        set u = FirstOfGroup(g)
        if u == null then
            call DestroyGroup(g)
            set g = null
            call MX_Say(p,"请先选择一个单位，以它的位置为创建位置。")
            return
        endif
        set u = CreateUnit(p,MX_Code(a),GetUnitX(u)+64,GetUnitY(u),0)
        call DestroyGroup(g)
        set g = null
        if u == null then
            call MX_Say(p,"游戏没有创建该单位。")
            return
        endif
        set u = null
    else
        call MX_Run(p,c,v,a,second)
        return
    endif
    call MX_Say(p,"命令已执行："+c+"。地图自身的触发器仍可能再次改变结果。")
endfunction

function MX_Chat takes nothing returns nothing
    local string text = GetEventPlayerChatString()
    if SubString(text,0,PREFIX_LENGTH) == "PREFIX" and (StringLength(text) == PREFIX_LENGTH or SubString(text,PREFIX_LENGTH,PREFIX_LENGTH+1) == " ") then
        call MX_Dispatch(GetTriggerPlayer(),SubString(text,PREFIX_LENGTH,StringLength(text)))
    endif
endfunction

function MX_Click takes nothing returns nothing
    local player p = GetTriggerPlayer()
    local integer id = GetPlayerId(p)
    local integer i = 0
    local button clicked = GetClickedButton()
    loop
        exitwhen i == 12
        if clicked == MX_buttons[id*12+i] then
            if MX_actions[id*12+i] != "" then
                call MX_Dispatch(p,MX_actions[id*12+i])
            endif
            set clicked = null
            set p = null
            return
        endif
        set i = i+1
    endloop
    set clicked = null
    set p = null
endfunction
'''
    functions = functions.replace('MENU_COUNT',str(len(options.features))).replace('PREFIX_LENGTH',str(len(options.prefix))).replace('PREFIX',options.prefix)

    init_names = []
    assignments = []
    for kind, key in enumerate(('item','unit','ability','upgrade')):
        codes = sorted({c for c in known.get(key,()) if len(c) == 4 and all(ch in ALPHABET for ch in c)})
        assignments.append(f'    set MX_counts[{kind}] = {len(codes)}\n')
        for i in range(0,len(codes),100):
            assignments.append(f'    set MX_ids{kind}[{i//100}] = '+quoted(''.join(codes[i:i+100]))+'\n')
    for i in range(0,len(assignments),40):
        name = 'MX_Ids'+str(i//40)
        init_names.append(name)
        functions += f'\nfunction {name} takes nothing returns nothing\n'+''.join(assignments[i:i+40])+'endfunction\n'
    functions += '''
function MX_Boot takes nothing returns nothing
    local trigger chat = null
    local trigger clicks = null
    local integer i = 0
    if MX_ready then
        return
    endif
    set MX_ready = true
'''
    for name in init_names:
        functions += f'    call ExecuteFunc("{name}")\n'
    functions += f'''    set MX_clock = CreateTimer()
    set chat = CreateTrigger()
    set clicks = CreateTrigger()
    call TriggerAddAction(chat,function MX_Chat)
    call TriggerAddAction(clicks,function MX_Click)
    loop
        exitwhen i == 12
        set MX_dialogs[i] = DialogCreate()
        call TriggerRegisterDialogEvent(clicks,MX_dialogs[i])
        call TriggerRegisterPlayerChatEvent(chat,Player(i),{quoted(options.prefix)},false)
        set i = i+1
    endloop
    set chat = null
    set clicks = null
endfunction
'''
    functions = functions.replace('RMinBJ(', 'MX_Min(').replace('RMaxBJ(', 'MX_Max(').replace('ModuloInteger(', 'MX_Mod(')
    from war3_jass_parser import tokens
    def namespace(raw):
        parsed = tokens(raw)
        for i in range(len(parsed)-1,-1,-1):
            token=parsed[i]
            replacement=None
            if token.kind == 'identifier' and token.value == b'code':
                replacement=b'objectId'
            elif token.kind == 'identifier' and token.value.startswith(b'MX_'):
                replacement=prefix.encode('ascii')+token.value[3:]
            elif (token.kind == 'string' and i >= 2 and parsed[i-1].value == b'('
                  and parsed[i-2].value == b'ExecuteFunc' and token.value.startswith(b'"MX_')):
                replacement=b'"'+prefix.encode('ascii')+token.value[4:]
            if replacement is not None:
                raw=raw[:token.start]+replacement+raw[token.end:]
        return raw
    # Rename symbols and our explicit ExecuteFunc targets. Rawcodes and ID
    # catalogue strings may themselves contain "MX_" and must remain exact.
    return namespace(globals_code.encode('utf-8')), namespace(functions.encode('utf-8'))


def usage(options):
    lines = ['地图功能使用说明', '', '功能脚本已写入地图。关闭或移走修改器后，以下功能仍由游戏独立执行。',
             '请从新副本的章节入口开始；旧存档不会自动获得新脚本。',
             '适用本地单人地图/战役；没有验收多人同步。支持前12个玩家槽位。',
             '', '输入 '+options.prefix+' 打开游戏内菜单；输入 '+options.prefix+' help 查看命令。',
             '例如：'+options.prefix+' gold '+str(options.resource_amount),
             '代码区分大小写。单位操作每次最多32个；自动项绑定执行时的选择，不随之后选择变化。',
             '3.0 背包仍由原有专用功能处理，本脚本不生成、删除或接管背包和扩展装备。', '']
    for cat in options.features:
        lines += [MENUS[cat][0]+'：', HELP[cat], '']
    lines += ['六神器方案：'+', '.join(options.artifact_codes),
              '物品/技能/单位代码须在当前章节中定义。技能等级超过定义、普通单位执行英雄操作等会跳过。',
              '基础复制只复制单位类型、所属玩家、英雄等级/基础三围及生命魔法比例；不复制物品、额外技能或扩展状态。',
              '数值范围：资源0-1亿；等级1-10000；技能1-100；人口0-300；大小0.05-10；经验倍率0-10；时间0-24。',
              '地图本身的剧情、触发器和合成机制仍会执行，并可能覆盖这些修改。']
    return '\n'.join(lines)+'\n'
