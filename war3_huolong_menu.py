"""Additional actions on HKE's own paginated main dialog, using classic JASS."""
import json
from war3_map_script_runtime import PRESETS, quoted

PAGE_SIZE = 6
# These are pages of the existing HKE main dialog, not another root menu.
PAGES = {
    10: ('物品槽操作', []),
    11: ('批量修改', [('恢复生命', 2100), ('恢复魔法', 2101), ('清除技能冷却', 2102),
        ('开启无敌', 2103), ('取消无敌', 2104), ('暂停单位', 2105), ('恢复行动', 2106),
        ('设置移动速度', 2107), ('设置朝向', 2108), ('设置模型大小', 2109)]),
    12: ('英雄成长', [('设置等级', 2200), ('设置经验', 2201), ('设置剩余技能点', 2202),
        ('设置基础力量', 2203), ('设置基础敏捷', 2204), ('设置基础智力', 2205), ('设置经验倍率', 2206)]),
    13: ('传送标记', [('保存位置一', 2300), ('保存位置二', 2301), ('保存位置三', 2302),
        ('传送到位置一', 2303), ('传送到位置二', 2304), ('传送到位置三', 2305),
        ('返回上次传送前的位置', 2306), ('选中部队向首个单位集合', 2307)]),
    14: ('资源与金矿', [('设置金币', 2400), ('设置木材', 2401), ('金币最低保有量（0关闭）', 2402),
        ('木材最低保有量（0关闭）', 2403), ('设置选中金矿金额', 2404),
        ('设置全图金矿金额', 2405), ('停止全图金矿处理', 2406), ('金币 +10000',2410),
        ('木材 +10000',2411), ('金币 +100000',2412), ('木材 +100000',2413)]),
    15: ('自动功能管理', [('当前选择自动回血', 2500), ('当前选择自动回魔', 2501),
        ('当前选择自动清冷却', 2502), ('停止增强自动回血', 2503), ('停止增强自动回魔', 2504),
        ('停止增强自动清冷却', 2505), ('回血触发百分比', 2506), ('回魔触发百分比', 2507),
        ('自动执行间隔（秒）', 2508), ('查看自动功能状态', 2509), ('停止全部增强自动项', 2510)]),
    16: ('收藏与最近使用', [('收藏物品', 2600), ('收藏技能', 2601), ('最近物品', 2602),
        ('最近技能', 2603), ('最近召唤', 2604), ('最近科技', 2605),
        ('收藏的常用功能',2606), ('管理常用功能收藏',2607), ('最近使用的功能',2608)]),
    17: ('清理本工具创建的对象', [('清理尚在地面的创建物品', 2700), ('清理本工具创建的普通单位', 2701)]),
    19: ('常用光环与被动', [('添加常用光环（最高有效等级）', 2800), ('添加常用被动（最高有效等级）', 2801)]),
    20: ('物品', [('放入普通物品栏', 3000), ('生成到附近地面', 3001), ('收藏／取消收藏', 3002)]),
    21: ('技能', [('添加／升到最高有效等级', 3100), ('添加／设置为指定等级', 3101),
        ('删除所选技能', 3102), ('收藏／取消收藏', 3103)]),
    22: ('召唤单位', [('召唤一个', 3200), ('指定召唤数量（1—12）', 3201)]),
    23: ('科技', [('研究一级', 3300), ('研究到最高等级', 3301), ('设置研究等级', 3302)]),
    30: ('所选物品槽', [('复制到空物品格', 3400), ('复制到附近地面', 3401),
        ('丢下这件物品', 3402), ('设置这件物品的充能', 3403)]),
}
MAIN = [('物品目录', 1000), ('技能目录', 1001), ('单位召唤目录', 1002), ('科技研究目录', 1003),
        ('领取六神器方案', 1100), ('物品槽操作', 1200), ('批量修改', 1201), ('英雄成长', 1202),
        ('传送标记', 1203), ('资源与金矿', 1204), ('自动功能管理', 1205),
        ('收藏与最近使用', 1206), ('清理创建记录', 1207), ('执行记录', 1208), ('常用光环与被动', 1209)]
ORIGINAL = [('资源菜单[A]', 'z2z', 65), ('自动化设置[B]', 'z4z', 66),
            ('选定单位特殊属性[C]', 'z5z', 67), ('个人选项设置[D]', 'z3z', 68),
            ('帮助菜单[E]', 'z9z', 69), ('其他玩家作弊管理[F]', 'z8z', 70),
            ('其他玩家管理[G]', 'z7z', 71), ('游戏作弊选项[H]', 'z6z', 72),
            ('关闭录像(无法再开)[L]', 'Zz0', 76)]


def _fragments(text, limit=300):
    chunks, current = [], ''
    for char in str(text).replace('\x00', ''):
        if len((current+char).encode('utf-8')) > limit:
            chunks.append(current)
            current = ''
        current += char
    if current or not chunks:
        chunks.append(current)
    return chunks


def _label(text):
    parts = _fragments(text,180)
    return parts[0]+('…' if len(parts)>1 else '')


def generate(options, known):
    records = known.get('catalogue', [])
    grouped = [[r for r in records if r['kind'] == kind] for kind in ('item', 'ability', 'unit', 'upgrade')]
    globals_code = r'''
gamecache hke_ExData = null
boolexpr hke_ExMineTest = null
group hke_ExReturnG = null
unit hke_ExReturnU = null
integer hke_ExP = 0
boolean hke_ExHandled = false
integer hke_ExBlocks = 0
integer hke_ExLoaded = 1
integer hke_ExTicks = 0
integer hke_ExRound = 0
real hke_ExTime = 0
integer array hke_ExCount
integer array hke_ExView
integer array hke_ExPage
integer array hke_ExHome
integer array hke_ExN
button array hke_ExButtons
integer array hke_ExActions
integer array hke_ExKind
integer array hke_ExEntry
integer array hke_ExDesc
integer array hke_ExMode
string array hke_ExQuery
integer array hke_ExScan
integer array hke_ExFound
integer array hke_ExPending
real array hke_ExUntil
group array hke_ExInput
integer array hke_ExInputSkip
integer array hke_ExChosen
integer array hke_ExSlot
unit array hke_ExHolder
item array hke_ExItem
string array hke_ExMessage
integer array hke_ExLogN
integer array hke_ExLogAt
integer array hke_ExConfirm
integer array hke_ExAmount
group array hke_ExMines
integer array hke_ExMineOK
integer array hke_ExMineBad
group array hke_ExAuto
real array hke_ExHP
real array hke_ExMP
real array hke_ExPeriod
real array hke_ExDue
integer array hke_ExGold
integer array hke_ExWood
real array hke_ExX
real array hke_ExY
boolean array hke_ExSaved
unit array hke_ExBefore
real array hke_ExBeforeX
real array hke_ExBeforeY
unit array hke_ExUnits
item array hke_ExItems
integer hke_ExSkip = 0
integer hke_ExOK = 0
integer hke_ExCounter = 0
string hke_ExWhy = ""
'''
    functions = r'''
function hke_ExRefresh takes integer p returns nothing
set hke_ExP=p
call ExecuteFunc("hke_ExRender")
endfunction
function hke_ExLive takes integer p, unit u returns boolean
return u != null and GetUnitTypeId(u) != 0 and GetOwningPlayer(u) == Player(p) and not IsUnitType(u,UNIT_TYPE_DEAD) and GetUnitAbilityLevel(u,'Aloc') == 0
endfunction
function hke_ExText takes integer k, integer n, string key returns string
return GetStoredString(hke_ExData,I2S(k),I2S(n)+key)
endfunction
function hke_ExInt takes integer k, integer n, string key returns integer
return GetStoredInteger(hke_ExData,I2S(k),I2S(n)+key)
endfunction
function hke_ExIndex takes integer k, integer id returns integer
return GetStoredInteger(hke_ExData,"id"+I2S(k),I2S(id))
endfunction
function hke_ExTake takes integer p, boolean owned returns group
local group all=CreateGroup()
local group picked=CreateGroup()
local unit u
local integer n=0
local integer visited=0
set hke_ExSkip=0
call GroupEnumUnitsSelected(all,Player(p),null)
loop
set u=FirstOfGroup(all)
exitwhen u == null or visited >= 256
call GroupRemoveUnit(all,u)
set visited=visited+1
if n < 32 and GetUnitTypeId(u) != 0 and (not owned or hke_ExLive(p,u)) then
call GroupAddUnit(picked,u)
set n=n+1
else
set hke_ExSkip=hke_ExSkip+1
endif
endloop
call DestroyGroup(all)
set all=null
set u=null
set hke_ExReturnG=picked
set picked=null
return hke_ExReturnG
endfunction
function hke_ExOne takes integer p returns unit
local group g=hke_ExTake(p,true)
local unit u=FirstOfGroup(g)
if u != null then
call GroupRemoveUnit(g,u)
if FirstOfGroup(g) != null then
set u=null
endif
endif
call DestroyGroup(g)
set g=null
set hke_ExReturnU=u
set u=null
return hke_ExReturnU
endfunction
function hke_ExResult takes integer p, string title, integer ok, integer bad, string why returns nothing
local integer at=ModuloInteger(hke_ExLogN[p],10)
set hke_ExMessage[p]=title+"|n成功："+I2S(ok)+"；跳过或未完成："+I2S(bad)+"|n"+why
if hke_ExData != null then
call StoreString(hke_ExData,"log"+I2S(p),I2S(at),hke_ExMessage[p])
endif
set hke_ExLogN[p]=hke_ExLogN[p]+1
set hke_ExView[p]=90
set hke_ExPage[p]=0
call hke_ExRefresh(p)
endfunction
function hke_ExCancelInput takes integer p returns nothing
set hke_ExPending[p]=0
if hke_ExInput[p] != null then
call DestroyGroup(hke_ExInput[p])
set hke_ExInput[p]=null
endif
endfunction
function hke_ExContains takes string source, string part returns boolean
local integer i=0
local integer n=StringLength(source)-StringLength(part)
loop
exitwhen i > n
if SubString(source,i,i+StringLength(part)) == part then
return true
endif
set i=i+1
endloop
return false
endfunction
function hke_ExListCount takes integer p returns integer
if hke_ExMode[p] == 0 and hke_ExQuery[p] == "" then
return hke_ExCount[hke_ExKind[p]]
endif
return hke_ExFound[p]
endfunction
function hke_ExListEntry takes integer p, integer n returns integer
if hke_ExMode[p] == 0 and hke_ExQuery[p] == "" then
return n
endif
return GetStoredInteger(hke_ExData,"result"+I2S(p),I2S(n))
endfunction
function hke_ExList takes integer p, integer k, integer mode returns nothing
set hke_ExKind[p]=k
set hke_ExMode[p]=mode
set hke_ExQuery[p]=""
set hke_ExFound[p]=0
set hke_ExScan[p]=1
set hke_ExView[p]=k+1
set hke_ExPage[p]=0
if mode == 0 then
set hke_ExScan[p]=0
endif
call hke_ExRefresh(p)
endfunction
function hke_ExAdd takes integer p, string label, integer action, integer key returns button
local integer at=p*10+hke_ExN[p]
set hke_ExButtons[at]=DialogAddButton(hke_zZ1[p],label,key)
set hke_ExActions[at]=action
set hke_ExN[p]=hke_ExN[p]+1
return hke_ExButtons[at]
endfunction
function hke_ExRow takes integer p, integer row, string label, integer action, integer key returns nothing
if row/6 == hke_ExPage[p] then
call hke_ExAdd(p,label,action,key)
endif
endfunction
function hke_ExRender takes nothing returns nothing
local integer p=hke_ExP
local integer view=hke_ExView[p]
local integer i=0
local integer total=0
local integer n=0
local integer k=hke_ExKind[p]
local integer selected=hke_ExEntry[p]
local integer pages=1
local integer perpage=6
local string title="主菜单"
local string label=""
local item it=null
if not hke_z4 or not hke_z6[p] then
return
endif
call hke_Z40Z(p,hke_zZ1[p],hke_ZZ1[p])
call DialogClear(hke_zZ1[p])
set hke_ExN[p]=0
__CLEAR_ORIGINAL__
if view == 0 then
__MAIN__
set hke_ExHome[p]=hke_ExPage[p]
elseif view >= 1 and view <= 4 then
set perpage=4
set k=view-1
set total=hke_ExListCount(p)
set title="主菜单 — "+hke_ExText(9,k,"n")+"（"+I2S(total)+"）"
if hke_ExLoaded < hke_ExBlocks then
set title=title+"|n目录准备中："+I2S(hke_ExLoaded)+" / "+I2S(hke_ExBlocks)
elseif hke_ExScan[p] > 0 then
set title=title+"|n正在筛选，可先查看已找到的结果"
endif
set i=hke_ExPage[p]*perpage+1
loop
exitwhen hke_ExLoaded < hke_ExBlocks or i > total or i > hke_ExPage[p]*perpage+perpage
set n=hke_ExListEntry(p,i)
call hke_ExAdd(p,hke_ExText(k,n,"n")+" ["+hke_ExText(k,n,"c")+"]",20000+n,0)
set i=i+1
endloop
call hke_ExAdd(p,"按名称／代码搜索 [S]",9100,83)
call hke_ExAdd(p,"全部／仅地图改动 [F]",9101,70)
elseif view == 10 then
set title="主菜单 — 物品槽操作（请先只选一个己方单位）"
set hke_ExHolder[p]=hke_ExOne(p)
set total=6
loop
exitwhen i >= 6
set it=hke_Slot(hke_ExHolder[p],i)
set label="空／受保护"
if it != null then
set label=GetItemName(it)
endif
call hke_ExAdd(p,"第"+I2S(i+1)+"格："+label,20000+i+1,49+i)
set i=i+1
endloop
elseif view >= 20 and view <= 23 then
set k=view-20
set title="主菜单 — "+hke_ExText(k,selected,"n")+" ["+hke_ExText(k,selected,"c")+"]|n"
set n=hke_ExInt(k,selected,"d")
if hke_ExDesc[p] >= n then
set hke_ExDesc[p]=0
endif
set title=title+hke_ExText(k,selected,"d"+I2S(hke_ExDesc[p]))
if k == 1 or k == 3 then
set title=title+"|n最高等级："+I2S(hke_ExInt(k,selected,"l"))
endif
if n > 1 then
call hke_ExAdd(p,"说明下一段 [D]",9102,68)
endif
__DETAIL__
call hke_ExAdd(p,"返回目录 [B]",9103,66)
elseif view == 18 then
set title="主菜单 — 执行记录"
set n=hke_ExLogN[p]-1-hke_ExLogAt[p]
if n >= 0 and hke_ExLogAt[p] < 10 then
set title=title+"|n"+GetStoredString(hke_ExData,"log"+I2S(p),I2S(ModuloInteger(n,10)))
else
set title=title+"|n暂无记录"
endif
call hke_ExAdd(p,"更早一条",9200,80)
call hke_ExAdd(p,"较新一条",9201,78)
elseif view == 80 then
set title="主菜单 — 确认操作|n"+hke_ExMessage[p]
call hke_ExAdd(p,"确认执行",9300,67)
elseif view == 90 then
set title="主菜单 — 执行结果|n"+hke_ExMessage[p]
elseif view == 30 then
set title="主菜单 — 第"+I2S(hke_ExSlot[p]+1)+"格物品"
if hke_ExItem[p] != null then
set title=title+"："+GetItemName(hke_ExItem[p])+"|n当前充能："+I2S(GetItemCharges(hke_ExItem[p]))
endif
__SLOT__
elseif view == 40 or view == 42 then
__FAVORITES__
elseif view == 41 then
set title="主菜单 — 最近使用的功能"
set total=0
set i=1
loop
exitwhen i > 9
set n=GetStoredInteger(hke_ExData,"oprecent"+I2S(p),I2S(i))
if n > 0 then
call hke_ExRow(p,total,GetStoredString(hke_ExData,"oplabels",I2S(n)),n,0)
set total=total+1
endif
set i=i+1
endloop
else
__PAGES__
endif
if total > perpage then
set pages=(total+perpage-1)/perpage
if hke_ExPage[p] > 0 then
call hke_ExAdd(p,"上一页 [P]",9001,80)
endif
if hke_ExPage[p]+1 < pages then
call hke_ExAdd(p,"下一页 [N]",9002,78)
endif
set title=title+"|n第"+I2S(hke_ExPage[p]+1)+" / "+I2S(pages)+"页"
endif
if view != 0 then
call hke_ExAdd(p,"返回主菜单 [R]",9003,82)
endif
call hke_ExAdd(p,"关闭 [X]",9004,88)
call DialogSetMessage(hke_zZ1[p],title+"|nHKE 1.25B · 原作者 火龙 / WuHansen")
call hke_Z44Z(p,Player(p),true)
set it=null
endfunction
function hke_ExMain takes nothing returns nothing
local integer p=hke_ExP
set hke_ExView[p]=0
set hke_ExPage[p]=hke_ExHome[p]
call hke_ExRefresh(p)
endfunction
function hke_ExRemember takes integer p, integer k, integer n returns nothing
local string area="recent"+I2S(p)+":"+I2S(k)
local integer i=9
loop
exitwhen i <= 1
call StoreInteger(hke_ExData,area,I2S(i),GetStoredInteger(hke_ExData,area,I2S(i-1)))
set i=i-1
endloop
call StoreInteger(hke_ExData,area,"1",n)
endfunction
function hke_ExTrackSlot takes integer p, boolean units returns integer
local integer i=p*128
loop
exitwhen i >= p*128+128
if units then
if hke_ExUnits[i] == null or GetUnitTypeId(hke_ExUnits[i]) == 0 then
return i
endif
elseif hke_ExItems[i] == null or GetItemTypeId(hke_ExItems[i]) == 0 then
return i
endif
set i=i+1
endloop
return -1
endfunction
function hke_ExGive takes integer p, unit u, integer n, boolean ground, integer charges returns boolean
local integer id=hke_ExInt(0,n,"i")
local integer slot=0
local integer track=hke_ExTrackSlot(p,false)
local item it=null
local real x=0
local real y=0
if not hke_ExLive(p,u) or id == 0 or hke_ProtectedItem(id) or track < 0 then
set hke_ExWhy="目标无效、物品受保护或创建记录已满。"
return false
endif
if not ground then
if hke_ExInt(0,n,"p") > 0 then
set hke_ExWhy="该物品拾取后即生效，请选择生成到地面。"
return false
endif
loop
exitwhen slot >= 6 or slot >= UnitInventorySize(u) or UnitItemInSlot(u,slot) == null
set slot=slot+1
endloop
if slot >= 6 or slot >= UnitInventorySize(u) then
set hke_ExWhy="物品栏已满／没有普通物品栏，未创建；可改选生成到地面。"
return false
endif
endif
set x=RMaxBJ(GetRectMinX(hke_z8)+32,RMinBJ(GetRectMaxX(hke_z8)-32,GetUnitX(u)+96))
set y=RMaxBJ(GetRectMinY(hke_z8)+32,RMinBJ(GetRectMaxY(hke_z8)-32,GetUnitY(u)))
set it=CreateItem(id,x,y)
if it == null or GetItemTypeId(it) != id then
set hke_ExWhy="游戏没有创建出该物品，可能未载入对应定义。"
set it=null
return false
endif
set hke_ExItems[track]=it
if charges >= 0 and (GetItemCharges(it) > 0 or hke_ExInt(0,n,"q") > 0) then
call SetItemCharges(it,charges)
endif
if not ground then
if not UnitAddItem(u,it) then
set hke_ExWhy="游戏未确认接收，创建物品已保留；请检查背包及目标附近，未删除或重复创建。"
set it=null
return false
endif
endif
set it=null
return true
endfunction
function hke_ExAbility takes integer p, unit u, integer n, integer level, boolean remove returns boolean
local integer id=hke_ExInt(1,n,"i")
local integer maximum=hke_ExInt(1,n,"l")
if not hke_ExLive(p,u) or id == 0 or hke_ProtectedAbility(id) then
set hke_ExWhy="目标无效或技能是背包控制能力。"
return false
endif
if remove then
if GetUnitAbilityLevel(u,id) == 0 then
set hke_ExWhy="单位没有该技能。"
return false
endif
call hke_RemoveAbility(u,id)
if GetUnitAbilityLevel(u,id) == 0 then
return true
endif
set hke_ExWhy="游戏未移除该技能，读回仍存在；没有重复调用。"
return false
endif
if level < 1 or level > maximum then
set hke_ExWhy="等级超过当前地图定义范围。"
return false
endif
if GetUnitAbilityLevel(u,id) == 0 then
if not hke_AddAbility(u,id) then
set hke_ExWhy="游戏拒绝添加该技能，已跳过；未重复尝试。"
return false
endif
call UnitMakeAbilityPermanent(u,true,id)
endif
call SetUnitAbilityLevel(u,id,level)
if GetUnitAbilityLevel(u,id) != level then
set hke_ExWhy="技能等级读回与目标不一致。"
return false
endif
return true
endfunction
function hke_ExSpawn takes integer p, integer n, integer amount, unit anchor returns nothing
local integer id=hke_ExInt(2,n,"i")
local integer i=0
local integer slot=0
local integer ok=0
local unit u=null
local real x=0
local real y=0
if not hke_ExLive(p,anchor) or id == 0 or hke_ExInt(2,n,"u") > 0 then
call hke_ExResult(p,"召唤单位",0,amount,"请只选一个己方单位作为位置；控制载体或不可选单位禁止召唤。")
return
endif
loop
exitwhen i >= amount
set slot=hke_ExTrackSlot(p,true)
if slot >= 0 then
set x=RMaxBJ(GetRectMinX(hke_z8)+32,RMinBJ(GetRectMaxX(hke_z8)-32,GetUnitX(anchor)+128+64*ModuloInteger(i,4)))
set y=RMaxBJ(GetRectMinY(hke_z8)+32,RMinBJ(GetRectMaxY(hke_z8)-32,GetUnitY(anchor)+64*(i/4)))
set u=CreateUnit(Player(p),id,x,y,GetUnitFacing(anchor))
if u != null and GetUnitTypeId(u) == id then
set hke_ExUnits[slot]=u
set ok=ok+1
endif
endif
set i=i+1
endloop
if ok > 0 then
call hke_ExRemember(p,2,n)
endif
call hke_ExResult(p,"召唤单位",ok,amount-ok,"单次最多12个；创建失败不重复执行，已有创建物保留。")
set u=null
endfunction
function hke_ExNumeric takes string s returns boolean
local integer i=0
local integer dots=0
local integer digits=0
local string c=""
if StringLength(s) == 0 or StringLength(s) > 12 then
return false
endif
loop
exitwhen i >= StringLength(s)
set c=SubString(s,i,i+1)
if c == "." then
set dots=dots+1
if dots > 1 then
return false
endif
elseif c == "-" and i == 0 then
else
if not hke_ExContains("0123456789",c) then
return false
endif
set digits=digits+1
endif
set i=i+1
endloop
return digits > 0 and digits <= 9
endfunction
function hke_ExRequest takes integer p, integer action, string prompt, boolean targets returns nothing
call hke_ExCancelInput(p)
set hke_ExPending[p]=action
set hke_ExUntil[p]=hke_ExTime+60
set hke_ExChosen[p]=hke_ExEntry[p]
if targets then
set hke_ExInput[p]=hke_ExTake(p,action != 2404)
set hke_ExInputSkip[p]=hke_ExSkip
endif
call hke_ExResult(p,"等待输入",0,0,prompt+"|n关闭对话框，在聊天输入：__INPUT__ 内容|n60秒内有效；点返回主菜单可取消。")
endfunction
function hke_ExApply takes integer p, integer action, real value, group g, integer chosen returns nothing
local unit u
local integer ok=0
local integer bad=hke_ExSkip
local integer n=0
local boolean done=false
set hke_ExWhy=""
loop
set u=FirstOfGroup(g)
exitwhen u == null or n >= 32
call GroupRemoveUnit(g,u)
set done=false
if hke_ExLive(p,u) then
if action == 2100 then
call SetUnitState(u,UNIT_STATE_LIFE,GetUnitState(u,UNIT_STATE_MAX_LIFE))
set done=GetUnitState(u,UNIT_STATE_LIFE) >= GetUnitState(u,UNIT_STATE_MAX_LIFE)-1
elseif action == 2101 then
call SetUnitState(u,UNIT_STATE_MANA,GetUnitState(u,UNIT_STATE_MAX_MANA))
set done=GetUnitState(u,UNIT_STATE_MANA) >= GetUnitState(u,UNIT_STATE_MAX_MANA)-1
elseif action == 2102 then
call UnitResetCooldown(u)
set done=true
elseif action == 2103 or action == 2104 then
call SetUnitInvulnerable(u,action == 2103)
set done=true
elseif action == 2105 or action == 2106 then
call PauseUnit(u,action == 2105)
set done=IsUnitPaused(u) == (action == 2105)
elseif action == 2107 then
call SetUnitMoveSpeed(u,value)
set done=RAbsBJ(GetUnitMoveSpeed(u)-value) < 1
elseif action == 2108 then
call SetUnitFacing(u,value)
set done=true
elseif action == 2109 then
call SetUnitScale(u,value,value,value)
set done=true
elseif action >= 2200 and action <= 2205 and IsUnitType(u,UNIT_TYPE_HERO) then
if action == 2200 then
call SetHeroLevel(u,R2I(value),false)
set done=GetHeroLevel(u) == R2I(value)
elseif action == 2201 then
call SetHeroXP(u,R2I(value),false)
set done=GetHeroXP(u) == R2I(value)
elseif action == 2202 then
call UnitModifySkillPoints(u,R2I(value)-GetHeroSkillPoints(u))
set done=GetHeroSkillPoints(u) == R2I(value)
elseif action == 2203 then
call SetHeroStr(u,R2I(value),true)
set done=GetHeroStr(u,false) == R2I(value)
elseif action == 2204 then
call SetHeroAgi(u,R2I(value),true)
set done=GetHeroAgi(u,false) == R2I(value)
else
call SetHeroInt(u,R2I(value),true)
set done=GetHeroInt(u,false) == R2I(value)
endif
elseif action == 3100 or action == 3101 or action == 3102 then
set done=hke_ExAbility(p,u,chosen,R2I(value),action == 3102)
endif
endif
if done then
set ok=ok+1
else
set bad=bad+1
endif
set n=n+1
endloop
call DestroyGroup(g)
if ok == 0 and bad == 0 then
set hke_ExWhy="没有可处理的己方单位。"
elseif hke_ExWhy == "" then
set hke_ExWhy="无法读回的冷却、无敌、朝向和缩放仅确认调用已执行；剧情触发器可能覆盖设置。"
endif
if ok > 0 and action >= 3100 and action <= 3102 then
call hke_ExRemember(p,1,chosen)
endif
call hke_ExResult(p,"单位操作",ok,bad,hke_ExWhy)
set u=null
endfunction
function hke_ExMove takes integer p, real x, real y, boolean back returns nothing
local group g=null
local unit u=null
local integer i=0
local integer at=0
local integer ok=0
local integer bad=0
local real tx=x
local real ty=y
if back then
set g=CreateGroup()
loop
exitwhen i >= 32
set at=p*32+i
if hke_ExBefore[at] != null then
call GroupAddUnit(g,hke_ExBefore[at])
endif
set i=i+1
endloop
else
set g=hke_ExTake(p,true)
endif
set i=0
loop
set u=FirstOfGroup(g)
exitwhen u == null or i >= 32
call GroupRemoveUnit(g,u)
set at=p*32+i
if back then
set at=p*32
loop
exitwhen at >= p*32+32 or hke_ExBefore[at] == u
set at=at+1
endloop
set tx=hke_ExBeforeX[at]
set ty=hke_ExBeforeY[at]
set hke_ExBefore[at]=null
else
set tx=x+64*ModuloInteger(i,4)
set ty=y+64*(i/4)
set hke_ExBefore[at]=u
set hke_ExBeforeX[at]=GetUnitX(u)
set hke_ExBeforeY[at]=GetUnitY(u)
endif
if hke_ExLive(p,u) and not IsUnitType(u,UNIT_TYPE_STRUCTURE) and not IsUnitLoaded(u) and tx >= GetRectMinX(hke_z8) and tx <= GetRectMaxX(hke_z8) and ty >= GetRectMinY(hke_z8) and ty <= GetRectMaxY(hke_z8) then
call SetUnitPosition(u,tx,ty)
if RAbsBJ(GetUnitX(u)-tx) < 96 and RAbsBJ(GetUnitY(u)-ty) < 96 then
set ok=ok+1
else
set bad=bad+1
endif
else
set bad=bad+1
endif
set i=i+1
endloop
if not back then
loop
exitwhen i >= 32
set hke_ExBefore[p*32+i]=null
set i=i+1
endloop
endif
call DestroyGroup(g)
call hke_ExResult(p,"传送",ok,bad,"按地图边界与通行性移动，单位分散落位；明显受阻计为未完成。返回只恢复位置，不撤销地图事件。")
set u=null
set g=null
endfunction
function hke_ExMine takes unit u returns boolean
local integer i=0
if u == null or GetUnitTypeId(u) == 0 or IsUnitType(u,UNIT_TYPE_DEAD) then
return false
endif
loop
exitwhen i >= hke_ExCount[8]
if GetUnitAbilityLevel(u,GetStoredInteger(hke_ExData,"gold",I2S(i))) > 0 then
return true
endif
set i=i+1
endloop
return false
endfunction
function hke_ExMineFilter takes nothing returns boolean
return hke_ExMine(GetFilterUnit())
endfunction
function hke_ExMineBatch takes integer p returns nothing
local unit u=null
local integer i=0
loop
set u=FirstOfGroup(hke_ExMines[p])
exitwhen u == null or i >= 32
call GroupRemoveUnit(hke_ExMines[p],u)
if hke_ExMine(u) then
call SetResourceAmount(u,hke_ExAmount[p])
if GetResourceAmount(u) == hke_ExAmount[p] then
set hke_ExMineOK[p]=hke_ExMineOK[p]+1
else
set hke_ExMineBad[p]=hke_ExMineBad[p]+1
endif
else
set hke_ExMineBad[p]=hke_ExMineBad[p]+1
endif
set i=i+1
endloop
if FirstOfGroup(hke_ExMines[p]) == null then
call DestroyGroup(hke_ExMines[p])
set hke_ExMines[p]=null
call hke_ExResult(p,"金矿金额处理完成",hke_ExMineOK[p],hke_ExMineBad[p],"只处理识别到金矿能力的单位，逐矿读回金额。")
endif
set u=null
endfunction
function hke_ExSlotValid takes integer p returns boolean
return hke_ExLive(p,hke_ExHolder[p]) and hke_ExItem[p] != null and GetItemTypeId(hke_ExItem[p]) != 0 and hke_Slot(hke_ExHolder[p],hke_ExSlot[p]) == hke_ExItem[p]
endfunction
function hke_ExResearch takes integer p, integer n, integer level returns nothing
local integer id=hke_ExInt(3,n,"i")
local integer current=GetPlayerTechCount(Player(p),id,true)
if id == 0 or level < current or level > hke_ExInt(3,n,"l") then
call hke_ExResult(p,"科技研究",0,1,"超出地图等级范围，或尝试降级科技。降级不能可靠撤销已生效的科技，未执行。")
return
endif
call SetPlayerTechResearched(Player(p),id,level)
if GetPlayerTechCount(Player(p),id,true) == level then
call hke_ExRemember(p,3,n)
call hke_ExResult(p,"科技研究",1,0,"已读回目标等级。")
else
call hke_ExResult(p,"科技研究",0,1,"游戏没有返回目标等级，未重复调用。")
endif
endfunction
function hke_ExCleanup takes integer p, boolean units returns nothing
local integer i=p*128
local integer ok=0
local integer bad=0
local unit u=null
local item it=null
loop
exitwhen i >= p*128+128
if units then
set u=hke_ExUnits[i]
if u != null and GetUnitTypeId(u) != 0 then
if GetOwningPlayer(u) == Player(p) and not hke_HasBag(u) then
call RemoveUnit(u)
if GetUnitTypeId(u) == 0 then
set ok=ok+1
set hke_ExUnits[i]=null
else
set bad=bad+1
endif
else
set bad=bad+1
endif
endif
else
set it=hke_ExItems[i]
if it != null and GetItemTypeId(it) != 0 then
if not IsItemOwned(it) and not hke_ProtectedItem(GetItemTypeId(it)) then
call RemoveItem(it)
if GetItemTypeId(it) == 0 then
set ok=ok+1
set hke_ExItems[i]=null
else
set bad=bad+1
endif
else
set bad=bad+1
endif
endif
endif
set i=i+1
endloop
call hke_ExResult(p,"清理创建记录",ok,bad,"只处理本增强功能的创建记录；已被持有的物品和3.0背包持有者保留。")
set u=null
set it=null
endfunction
function hke_ExCountOne takes nothing returns nothing
if GetUnitTypeId(GetEnumUnit()) != 0 then
set hke_ExCounter=hke_ExCounter+1
endif
endfunction
function hke_ExAutoStatus takes integer p returns nothing
local integer i=0
local string s=""
loop
exitwhen i >= 3
set s=s+hke_ExText(9,i,"a")+"："
if hke_ExAuto[p*3+i] == null then
set s=s+"关闭|n"
else
set hke_ExCounter=0
call ForGroup(hke_ExAuto[p*3+i],function hke_ExCountOne)
set s=s+"开启（绑定"+I2S(hke_ExCounter)+"个单位）|n"
endif
set i=i+1
endloop
set s=s+"回血阈值 "+R2SW(hke_ExHP[p],0,0)+"%；回魔阈值 "+R2SW(hke_ExMP[p],0,0)+"%|n间隔 "+R2SW(hke_ExPeriod[p],0,2)+" 秒|n金币下限 "+I2S(hke_ExGold[p])+"；木材下限 "+I2S(hke_ExWood[p])
call hke_ExResult(p,"增强自动项状态",1,0,s)
endfunction
function hke_ExStop takes integer p returns nothing
local integer i=0
loop
exitwhen i >= 3
if hke_ExAuto[p*3+i] != null then
call DestroyGroup(hke_ExAuto[p*3+i])
set hke_ExAuto[p*3+i]=null
endif
set i=i+1
endloop
set hke_ExGold[p]=0
set hke_ExWood[p]=0
endfunction
'''
    # Function bodies with generated presets keep actual map-specific levels.
    functions += '''function hke_ExBundle takes integer p, integer bundle returns nothing
local group g=hke_ExTake(p,true)
local unit u=null
local integer n=0
local integer ok=0
local integer bad=hke_ExSkip
set hke_ExWhy=""
loop
set u=FirstOfGroup(g)
exitwhen u == null
call GroupRemoveUnit(g,u)
'''
    for bundle, codes in enumerate(PRESETS.values()):
        functions += ('if' if bundle == 0 else 'elseif') + f' bundle == {bundle} then\n'
        for code in codes:
            functions += f'''set n=hke_ExIndex(1,'{code}')
if n > 0 and hke_ExAbility(p,u,n,hke_ExInt(1,n,"l"),false) then
set ok=ok+1
else
set bad=bad+1
endif
'''
    functions += '''endif
endloop
call DestroyGroup(g)
call hke_ExResult(p,"常用光环／被动",ok,bad,"逐技能添加并读回，按当前地图最高等级设置。"+hke_ExWhy)
set g=null
set u=null
endfunction
'''
    functions += r'''
function hke_ExAction takes integer p, integer action returns nothing
local integer n=hke_ExEntry[p]
local integer k=hke_ExKind[p]
local integer i=0
local integer ok=0
local integer bad=0
local integer id=0
local unit u=null
local group g=null
local item it=null
local boolean state=false
if hke_ExData == null or hke_ExLoaded < hke_ExBlocks then
call hke_ExResult(p,"目录仍在准备",0,1,"请稍后再执行新增功能；原版火龙功能仍可使用。")
return
endif
if GetStoredString(hke_ExData,"oplabels",I2S(action)) != "" then
set i=9
loop
exitwhen i <= 1
call StoreInteger(hke_ExData,"oprecent"+I2S(p),I2S(i),GetStoredInteger(hke_ExData,"oprecent"+I2S(p),I2S(i-1)))
set i=i-1
endloop
call StoreInteger(hke_ExData,"oprecent"+I2S(p),"1",action)
endif
if action >= 1000 and action <= 1003 then
call hke_ExList(p,action-1000,0)
elseif action >= 1200 and action <= 1209 then
set hke_ExView[p]=action-1190
set hke_ExPage[p]=0
set hke_ExLogAt[p]=0
call hke_ExRefresh(p)
elseif action >= 2100 and action <= 2106 then
set g=hke_ExTake(p,true)
call hke_ExApply(p,action,0,g,n)
elseif action >= 2107 and action <= 2109 then
call hke_ExRequest(p,action,"速度0—522；朝向0—360；模型大小0.1—10。",true)
elseif action >= 2200 and action <= 2205 then
call hke_ExRequest(p,action,"等级1—10000；经验0—1亿；技能点0—10000；基础三围0—100万。",true)
elseif action == 2206 then
call hke_ExRequest(p,action,"经验倍率0—100；只影响引擎经验分配。",false)
elseif action >= 2300 and action <= 2302 then
set u=hke_ExOne(p)
if u == null then
call hke_ExResult(p,"保存位置",0,1,"请只选一个己方单位作为位置。")
else
set i=p*3+action-2300
set hke_ExX[i]=GetUnitX(u)
set hke_ExY[i]=GetUnitY(u)
set hke_ExSaved[i]=true
call hke_ExResult(p,"保存位置",1,0,"位置"+I2S(action-2299)+"已记录，当前章节内可用。")
endif
elseif action >= 2303 and action <= 2305 then
set i=p*3+action-2303
if hke_ExSaved[i] then
call hke_ExMove(p,hke_ExX[i],hke_ExY[i],false)
else
call hke_ExResult(p,"传送",0,1,"这个位置还没有保存。")
endif
elseif action == 2306 then
call hke_ExMove(p,0,0,true)
elseif action == 2307 then
set g=hke_ExTake(p,true)
set u=FirstOfGroup(g)
if u != null then
call hke_ExMove(p,GetUnitX(u),GetUnitY(u),false)
else
call hke_ExResult(p,"部队集合",0,1,"没有选择可集合的己方单位。")
endif
call DestroyGroup(g)
elseif action >= 2400 and action <= 2405 then
call hke_ExRequest(p,action,"请输入0—1亿的整数；0可用于关闭资源最低值维持。",action == 2404)
elseif action == 2406 then
if hke_ExMines[p] != null then
call DestroyGroup(hke_ExMines[p])
set hke_ExMines[p]=null
endif
call hke_ExResult(p,"停止金矿处理",1,0,"已完成的金额保留，后续不再处理。")
elseif action >= 2410 and action <= 2413 then
set i=10000
if action >= 2412 then
set i=100000
endif
if ModuloInteger(action,2) == 0 then
set id=GetPlayerState(Player(p),PLAYER_STATE_RESOURCE_GOLD)
if id <= 100000000-i then
call SetPlayerState(Player(p),PLAYER_STATE_RESOURCE_GOLD,id+i)
if GetPlayerState(Player(p),PLAYER_STATE_RESOURCE_GOLD) == id+i then
set ok=1
endif
endif
else
set id=GetPlayerState(Player(p),PLAYER_STATE_RESOURCE_LUMBER)
if id <= 100000000-i then
call SetPlayerState(Player(p),PLAYER_STATE_RESOURCE_LUMBER,id+i)
if GetPlayerState(Player(p),PLAYER_STATE_RESOURCE_LUMBER) == id+i then
set ok=1
endif
endif
endif
call hke_ExResult(p,"增加资源",ok,1-ok,"上限1亿；超过范围或读回不同则计为未完成。")
elseif action >= 2500 and action <= 2502 then
set i=p*3+action-2500
if hke_ExAuto[i] != null then
call DestroyGroup(hke_ExAuto[i])
endif
set hke_ExAuto[i]=hke_ExTake(p,true)
if FirstOfGroup(hke_ExAuto[i]) == null then
call DestroyGroup(hke_ExAuto[i])
set hke_ExAuto[i]=null
call hke_ExResult(p,"启用增强自动项",0,1,"没有选择可绑定的己方单位。")
else
call hke_ExAutoStatus(p)
endif
elseif action >= 2503 and action <= 2505 then
set i=p*3+action-2503
if hke_ExAuto[i] != null then
call DestroyGroup(hke_ExAuto[i])
set hke_ExAuto[i]=null
endif
call hke_ExAutoStatus(p)
elseif action >= 2506 and action <= 2508 then
call hke_ExRequest(p,action,"血魔阈值1—100%；执行间隔0.25—10秒。",false)
elseif action == 2509 then
call hke_ExAutoStatus(p)
elseif action == 2510 then
call hke_ExStop(p)
call hke_ExAutoStatus(p)
elseif action >= 2600 and action <= 2605 then
set k=action-2602
set i=3
if action < 2602 then
set k=action-2600
set i=2
endif
call hke_ExList(p,k,i)
elseif action >= 2606 and action <= 2608 then
set hke_ExView[p]=40
if action == 2607 then
set hke_ExView[p]=42
elseif action == 2608 then
set hke_ExView[p]=41
endif
set hke_ExPage[p]=0
call hke_ExRefresh(p)
elseif action == 2700 or action == 2701 then
set hke_ExConfirm[p]=action
set hke_ExMessage[p]="只清理本工具创建记录中的对象，已被持有的物品／带3.0背包的单位保留。此操作不会撤销相关地图事件。"
set hke_ExView[p]=80
call hke_ExRefresh(p)
elseif action == 2800 or action == 2801 then
call hke_ExBundle(p,action-2800)
elseif action == 1100 or action == 3000 or action == 3001 or action == 3400 or action == 3401 then
set u=hke_ExOne(p)
set hke_ExWhy=""
if action == 1100 then
__ARTIFACTS__
elseif action == 3000 or action == 3001 then
if hke_ExGive(p,u,n,action == 3001,-1) then
set ok=1
call hke_ExRemember(p,0,n)
else
set bad=1
endif
elseif hke_ExSlotValid(p) then
set n=hke_ExIndex(0,GetItemTypeId(hke_ExItem[p]))
if hke_ExGive(p,hke_ExHolder[p],n,action == 3401,GetItemCharges(hke_ExItem[p])) then
set ok=1
else
set bad=1
endif
else
set bad=1
set hke_ExWhy="原物品已变化，请重新选择物品槽。"
endif
if ok == 0 and hke_ExWhy == "" then
set hke_ExWhy="请只选一个己方单位，且物品必须存在于当前章节定义中。"
endif
call hke_ExResult(p,"生成物品",ok,bad,hke_ExWhy)
elseif action == 3002 or action == 3103 then
set state=GetStoredInteger(hke_ExData,"fav"+I2S(p)+":"+I2S(k),I2S(n)) == 0
if state then
call StoreInteger(hke_ExData,"fav"+I2S(p)+":"+I2S(k),I2S(n),1)
else
call StoreInteger(hke_ExData,"fav"+I2S(p)+":"+I2S(k),I2S(n),0)
endif
call hke_ExResult(p,"更新收藏",1,0,"收藏已在当前章节记录；重新打开收藏目录即可查看。")
elseif action == 3100 or action == 3102 then
set g=hke_ExTake(p,true)
call hke_ExApply(p,action,hke_ExInt(1,n,"l"),g,n)
elseif action == 3101 then
call hke_ExRequest(p,action,"输入1—"+I2S(hke_ExInt(1,n,"l"))+"的整数。",true)
elseif action == 3200 then
call hke_ExSpawn(p,n,1,hke_ExOne(p))
elseif action == 3201 then
call hke_ExRequest(p,action,"召唤数量1—12；请只选一个己方单位定位。",true)
elseif action == 3300 then
call hke_ExResearch(p,n,GetPlayerTechCount(Player(p),hke_ExInt(3,n,"i"),true)+1)
elseif action == 3301 then
call hke_ExResearch(p,n,hke_ExInt(3,n,"l"))
elseif action == 3302 then
call hke_ExRequest(p,action,"科技等级0—"+I2S(hke_ExInt(3,n,"l"))+"；不支持降级撤销效果。",false)
elseif action == 3402 then
if hke_ExSlotValid(p) and hke_ExInt(0,hke_ExIndex(0,GetItemTypeId(hke_ExItem[p])),"r") > 0 then
call UnitRemoveItem(hke_ExHolder[p],hke_ExItem[p])
if hke_Slot(hke_ExHolder[p],hke_ExSlot[p]) != hke_ExItem[p] then
set ok=1
endif
endif
call hke_ExResult(p,"丢下物品",ok,1-ok,"只能处理仍在原槽位、定义允许丢下的普通物品。")
elseif action == 3403 then
call hke_ExRequest(p,action,"充能1—100000；只修改有充能的原物品。",false)
endif
set u=null
set g=null
set it=null
endfunction
function hke_ExClick takes nothing returns nothing
local integer p=hke_ExP
local integer i=0
local integer action=0
local integer old=hke_ExView[p]
local button b=GetClickedButton()
loop
exitwhen i >= hke_ExN[p]
if hke_ExButtons[p*10+i] == b then
set action=hke_ExActions[p*10+i]
endif
set i=i+1
endloop
if action < 1000 then
set b=null
return
endif
set hke_ExHandled=true
call hke_Z44Z(p,Player(p),false)
if not hke_z4 or not hke_z6[p] then
set b=null
return
endif
if action != 9004 then
call hke_ExCancelInput(p)
endif
if action == 9001 then
set hke_ExPage[p]=IMaxBJ(0,hke_ExPage[p]-1)
call hke_ExRefresh(p)
elseif action == 9002 then
set hke_ExPage[p]=hke_ExPage[p]+1
call hke_ExRefresh(p)
elseif action == 9003 then
set hke_ExView[p]=0
set hke_ExPage[p]=hke_ExHome[p]
call hke_ExRefresh(p)
elseif action == 9004 then
elseif action == 9100 then
call hke_ExRequest(p,9100,"搜索当前目录的名称或4位代码；输入 * 恢复全部。",false)
elseif action == 9101 then
set i=1
if hke_ExMode[p] == 1 then
set i=0
endif
call hke_ExList(p,hke_ExKind[p],i)
elseif action == 9102 then
set hke_ExDesc[p]=hke_ExDesc[p]+1
call hke_ExRefresh(p)
elseif action == 9103 then
set hke_ExView[p]=hke_ExKind[p]+1
call hke_ExRefresh(p)
elseif action == 9200 or action == 9201 then
if action == 9200 then
set hke_ExLogAt[p]=IMinBJ(9,IMinBJ(hke_ExLogN[p]-1,hke_ExLogAt[p]+1))
else
set hke_ExLogAt[p]=IMaxBJ(0,hke_ExLogAt[p]-1)
endif
call hke_ExRefresh(p)
elseif action == 9300 then
if hke_ExConfirm[p] == 2700 or hke_ExConfirm[p] == 2701 then
call hke_ExCleanup(p,hke_ExConfirm[p] == 2701)
elseif hke_ExConfirm[p] == 2405 then
if hke_ExMines[p] == null then
set hke_ExMines[p]=CreateGroup()
set hke_ExMineOK[p]=0
set hke_ExMineBad[p]=0
call GroupEnumUnitsInRect(hke_ExMines[p],hke_z8,hke_ExMineTest)
call hke_ExResult(p,"全图金矿任务已开始",0,0,"将分批处理，完成后显示实际读回结果；可从主菜单停止。")
else
call hke_ExResult(p,"全图金矿任务",0,1,"已有任务运行，请先等待完成或停止；没有叠加执行。")
endif
endif
set hke_ExConfirm[p]=0
elseif action >= 1000000 then
set i=action-1000000
if GetStoredInteger(hke_ExData,"opfav"+I2S(p),I2S(i)) == 0 then
call StoreInteger(hke_ExData,"opfav"+I2S(p),I2S(i),1)
else
call StoreInteger(hke_ExData,"opfav"+I2S(p),I2S(i),0)
endif
call hke_ExRefresh(p)
elseif action >= 20000 then
if old >= 1 and old <= 4 then
set hke_ExEntry[p]=action-20000
set hke_ExDesc[p]=0
set hke_ExView[p]=old+19
set hke_ExPage[p]=0
call hke_ExRefresh(p)
elseif old == 10 then
set hke_ExSlot[p]=action-20001
set hke_ExItem[p]=hke_Slot(hke_ExHolder[p],hke_ExSlot[p])
if not hke_ExSlotValid(p) then
call hke_ExResult(p,"选择物品槽",0,1,"该槽为空、受保护或目标已变化。")
else
set hke_ExView[p]=30
set hke_ExPage[p]=0
call hke_ExRefresh(p)
endif
endif
else
call hke_ExAction(p,action)
endif
set b=null
endfunction
function hke_ExChat takes nothing returns nothing
local integer p=GetPlayerId(GetTriggerPlayer())
local string text=GetEventPlayerChatString()
local string value=""
local integer action=hke_ExPending[p]
local integer n=hke_ExChosen[p]
local integer id=0
local integer ok=0
local integer bad=0
local integer count=0
local real number=0
local boolean valid=false
local group g=null
local unit u=null
if not hke_z4 or not hke_z6[p] or action == 0 or hke_ExTime > hke_ExUntil[p] or SubString(text,0,__INPUT_LEN__) != "__INPUT__ " then
return
endif
set value=SubString(text,__INPUT_LEN__,StringLength(text))
if action == 9100 then
set hke_ExQuery[p]=StringCase(value,false)
if value == "*" then
set hke_ExQuery[p]=""
endif
set hke_ExMode[p]=0
set hke_ExFound[p]=0
set hke_ExScan[p]=1
set hke_ExPage[p]=0
set hke_ExView[p]=hke_ExKind[p]+1
set id=GetStoredInteger(hke_ExData,"code"+I2S(hke_ExKind[p]),value)
if id > 0 then
set hke_ExFound[p]=1
call StoreInteger(hke_ExData,"result"+I2S(p),"1",id)
set hke_ExScan[p]=0
endif
if hke_ExQuery[p] == "" then
set hke_ExScan[p]=0
endif
call hke_ExCancelInput(p)
call hke_ExRefresh(p)
return
endif
if not hke_ExNumeric(value) then
call hke_ExResult(p,"输入无效",0,1,"请按提示输入普通数字，不能含单位、指数或其他字符。")
return
endif
set number=S2R(value)
set valid=number >= 0 and number <= 100000000 and number == I2R(R2I(number))
if action == 2107 then
set valid=number >= 0 and number <= 522
elseif action == 2108 then
set valid=number >= 0 and number <= 360
elseif action == 2109 then
set valid=number >= 0.1 and number <= 10
elseif action == 2200 then
set valid=valid and number >= 1 and number <= 10000
elseif action == 2202 then
set valid=valid and number <= 10000
elseif action >= 2203 and action <= 2205 then
set valid=valid and number <= 1000000
elseif action == 2206 then
set valid=number >= 0 and number <= 100
elseif action == 2506 or action == 2507 then
set valid=number >= 1 and number <= 100
elseif action == 2508 then
set valid=number >= 0.25 and number <= 10
elseif action == 3101 then
set valid=valid and number >= 1 and number <= hke_ExInt(1,n,"l")
elseif action == 3201 then
set valid=valid and number >= 1 and number <= 12
elseif action == 3302 then
set valid=valid and number <= hke_ExInt(3,n,"l")
elseif action == 3403 then
set valid=valid and number >= 1 and number <= 100000
endif
if not valid then
call hke_ExResult(p,"数值超出范围",0,1,"本次没有执行，请按刚才提示的范围重新输入。")
return
endif
set hke_ExPending[p]=0
set g=hke_ExInput[p]
set hke_ExInput[p]=null
if action >= 2107 and action <= 2205 or action == 3101 then
set hke_ExSkip=hke_ExInputSkip[p]
call hke_ExApply(p,action,number,g,n)
set g=null
elseif action == 2206 then
call SetPlayerHandicapXP(Player(p),number)
if RAbsBJ(GetPlayerHandicapXP(Player(p))-number) < 0.001 then
set ok=1
endif
call hke_ExResult(p,"经验倍率",ok,1-ok,"仅影响当前玩家的引擎经验；地图自编经验可能不采用此倍率。")
elseif action >= 2400 and action <= 2403 then
if action == 2400 then
call SetPlayerState(Player(p),PLAYER_STATE_RESOURCE_GOLD,R2I(number))
set ok=GetPlayerState(Player(p),PLAYER_STATE_RESOURCE_GOLD)
elseif action == 2401 then
call SetPlayerState(Player(p),PLAYER_STATE_RESOURCE_LUMBER,R2I(number))
set ok=GetPlayerState(Player(p),PLAYER_STATE_RESOURCE_LUMBER)
elseif action == 2402 then
set hke_ExGold[p]=R2I(number)
set ok=hke_ExGold[p]
else
set hke_ExWood[p]=R2I(number)
set ok=hke_ExWood[p]
endif
if ok == R2I(number) then
set ok=1
else
set ok=0
endif
call hke_ExResult(p,"资源设置",ok,1-ok,"金额／最低保有量已检查。最低值为0时关闭维持。")
elseif action == 2404 then
loop
set u=FirstOfGroup(g)
exitwhen u == null or count >= 32
call GroupRemoveUnit(g,u)
if hke_ExMine(u) then
call SetResourceAmount(u,R2I(number))
if GetResourceAmount(u) == R2I(number) then
set ok=ok+1
else
set bad=bad+1
endif
else
set bad=bad+1
endif
set count=count+1
endloop
call hke_ExResult(p,"选中金矿",ok,bad,"只对识别到金矿能力的单位写入并读回。")
elseif action == 2405 then
set hke_ExAmount[p]=R2I(number)
set hke_ExConfirm[p]=2405
set hke_ExMessage[p]="将当前章节全图金矿剩余金额设置为 "+I2S(R2I(number))+"。原金额不能通过取消任务自动还原。"
set hke_ExView[p]=80
call hke_ExRefresh(p)
elseif action == 2506 or action == 2507 or action == 2508 then
if action == 2506 then
set hke_ExHP[p]=number
elseif action == 2507 then
set hke_ExMP[p]=number
else
set hke_ExPeriod[p]=number
endif
call hke_ExAutoStatus(p)
elseif action == 3201 then
set u=FirstOfGroup(g)
if u != null then
call GroupRemoveUnit(g,u)
if FirstOfGroup(g) != null then
set u=null
endif
endif
call hke_ExSpawn(p,n,R2I(number),u)
elseif action == 3302 then
call hke_ExResearch(p,n,R2I(number))
elseif action == 3403 then
if hke_ExSlotValid(p) and (GetItemCharges(hke_ExItem[p]) > 0 or hke_ExInt(0,hke_ExIndex(0,GetItemTypeId(hke_ExItem[p])),"q") > 0) then
call SetItemCharges(hke_ExItem[p],R2I(number))
if GetItemCharges(hke_ExItem[p]) == R2I(number) then
set ok=1
endif
endif
call hke_ExResult(p,"修改物品充能",ok,1-ok,"只修改仍在原槽位的充能物品；普通装备不被改成消耗品。")
endif
if g != null then
call DestroyGroup(g)
endif
set g=null
set u=null
endfunction
function hke_ExSearch takes integer p returns nothing
local integer n=hke_ExScan[p]
local integer k=hke_ExKind[p]
local integer stop=IMinBJ(n+16,hke_ExCount[k]+1)
local boolean match=false
local integer j=0
local string text=""
loop
exitwhen n >= stop
set match=false
if hke_ExMode[p] == 1 then
set match=hke_ExInt(k,n,"m") > 0
elseif hke_ExMode[p] == 2 then
set match=GetStoredInteger(hke_ExData,"fav"+I2S(p)+":"+I2S(k),I2S(n)) > 0
elseif hke_ExMode[p] == 3 then
set j=1
loop
exitwhen j > 9
if GetStoredInteger(hke_ExData,"recent"+I2S(p)+":"+I2S(k),I2S(j)) == n then
set match=true
endif
set j=j+1
endloop
else
set text=StringCase(hke_ExText(k,n,"c")+" "+SubString(hke_ExText(k,n,"n"),0,96),false)
set match=hke_ExContains(text,hke_ExQuery[p])
endif
if match then
set hke_ExFound[p]=hke_ExFound[p]+1
call StoreInteger(hke_ExData,"result"+I2S(p),I2S(hke_ExFound[p]),n)
endif
set n=n+1
endloop
set hke_ExScan[p]=n
if n > hke_ExCount[k] then
set hke_ExScan[p]=0
if hke_ExView[p] == k+1 then
call hke_ExRefresh(p)
endif
endif
endfunction
function hke_ExAutoTick takes integer p returns nothing
local integer i=0
local integer j=0
local group g=null
local group keep=null
local unit u=null
local real maximum=0
if hke_ExTime < hke_ExDue[p] then
return
endif
set hke_ExDue[p]=hke_ExTime+hke_ExPeriod[p]
if hke_ExGold[p] > 0 and GetPlayerState(Player(p),PLAYER_STATE_RESOURCE_GOLD) < hke_ExGold[p] then
call SetPlayerState(Player(p),PLAYER_STATE_RESOURCE_GOLD,hke_ExGold[p])
endif
if hke_ExWood[p] > 0 and GetPlayerState(Player(p),PLAYER_STATE_RESOURCE_LUMBER) < hke_ExWood[p] then
call SetPlayerState(Player(p),PLAYER_STATE_RESOURCE_LUMBER,hke_ExWood[p])
endif
loop
exitwhen i >= 3
set g=hke_ExAuto[p*3+i]
if g != null then
set keep=CreateGroup()
set j=0
loop
set u=FirstOfGroup(g)
exitwhen u == null or j >= 32
call GroupRemoveUnit(g,u)
if hke_ExLive(p,u) then
call GroupAddUnit(keep,u)
if i == 0 then
set maximum=GetUnitState(u,UNIT_STATE_MAX_LIFE)
if GetUnitState(u,UNIT_STATE_LIFE)*100 < maximum*hke_ExHP[p] then
call SetUnitState(u,UNIT_STATE_LIFE,maximum)
endif
elseif i == 1 then
set maximum=GetUnitState(u,UNIT_STATE_MAX_MANA)
if GetUnitState(u,UNIT_STATE_MANA)*100 < maximum*hke_ExMP[p] then
call SetUnitState(u,UNIT_STATE_MANA,maximum)
endif
else
call UnitResetCooldown(u)
endif
elseif u != null and GetUnitTypeId(u) != 0 and GetOwningPlayer(u) == Player(p) then
call GroupAddUnit(keep,u)
endif
set j=j+1
endloop
call DestroyGroup(g)
set hke_ExAuto[p*3+i]=keep
endif
set i=i+1
endloop
set g=null
set keep=null
set u=null
endfunction
function hke_ExPulse takes nothing returns nothing
local integer p=0
set hke_ExTime=hke_ExTime+0.05
set hke_ExTicks=hke_ExTicks+1
if hke_ExLoaded < hke_ExBlocks then
call ExecuteFunc("hke_Ids"+I2S(hke_ExLoaded))
set hke_ExLoaded=hke_ExLoaded+1
if hke_ExLoaded >= hke_ExBlocks then
loop
exitwhen p >= 12
if hke_ExView[p] >= 1 and hke_ExView[p] <= 4 then
call hke_ExRefresh(p)
endif
set p=p+1
endloop
set p=0
endif
endif
loop
exitwhen p >= 12
if hke_ExPending[p] != 0 and hke_ExUntil[p] < hke_ExTime then
call hke_ExCancelInput(p)
call DisplayTimedTextToPlayer(Player(p),0,0,8,"火龙：等待输入已超时，本次操作取消。")
endif
if hke_ExLoaded >= hke_ExBlocks and hke_ExScan[p] > 0 then
call hke_ExSearch(p)
endif
set p=p+1
endloop
if ModuloInteger(hke_ExTicks,5) == 0 then
set p=0
loop
exitwhen p >= 12
if hke_z4 and hke_z6[p] then
call hke_ExAutoTick(p)
if hke_ExMines[p] != null then
call hke_ExMineBatch(p)
endif
endif
set p=p+1
endloop
endif
endfunction
function hke_ExInit takes nothing returns nothing
local integer p=0
local trigger chat=CreateTrigger()
local timer pulse=CreateTimer()
set hke_ExData=InitGameCache("__CACHE__")
if hke_ExData == null then
return
endif
call FlushGameCache(hke_ExData)
set hke_ExMineTest=Condition(function hke_ExMineFilter)
call ExecuteFunc("hke_Ids0")
loop
exitwhen p >= 12
set hke_ExHP[p]=50
set hke_ExMP[p]=50
set hke_ExPeriod[p]=0.5
set hke_ExQuery[p]=""
call TriggerRegisterPlayerChatEvent(chat,Player(p),"__INPUT__ ",false)
set p=p+1
endloop
call TriggerAddAction(chat,function hke_ExChat)
call TimerStart(pulse,0.05,true,function hke_ExPulse)
set chat=null
set pulse=null
endfunction
'''
    clear = '\n'.join('set hke_'+key+'[p]=null' for _, key, _ in ORIGINAL)
    main = ''
    for index, (label, key, hotkey) in enumerate(ORIGINAL):
        condition = 'true' if index < 5 else ('Player(p) == hke_z5' if index < 8 else 'Player(p) == hke_z5 and hke_z13')
        main += f'''if {condition} then
if total/6 == hke_ExPage[p] then
set hke_{key}[p]=hke_ExAdd(p,{quoted(label)},0,{hotkey})
endif
set total=total+1
endif
'''
    for label, action in MAIN:
        main += f'call hke_ExRow(p,total,{quoted(label)},{action},0)\nset total=total+1\n'
    page_code = ''
    for view, (title, rows) in PAGES.items():
        if view in (10, 20, 21, 22, 23, 30):
            continue
        page_code += f'if view == {view} then\nset title={quoted("主菜单 — "+title)}\nset total={len(rows)}\n'
        page_code += ''.join(f'call hke_ExRow(p,{i},{quoted(label)},{action},0)\n' for i, (label, action) in enumerate(rows))
        page_code += 'endif\n'
    detail = ''
    for view in range(20, 24):
        detail += f'if view == {view} then\n'
        detail += ''.join(f'call hke_ExAdd(p,{quoted(label)},{action},0)\n' for label, action in PAGES[view][1])
        detail += 'endif\n'
    slot = ''.join(f'call hke_ExAdd(p,{quoted(label)},{action},0)\n' for label, action in PAGES[30][1])
    artifacts = ''
    for code in options.artifact_codes:
        artifacts += f'''set n=hke_ExIndex(0,'{code}')
if hke_ExGive(p,u,n,false,-1) then
set ok=ok+1
else
set bad=bad+1
endif
'''
    operations=dict((action,label) for label,action in MAIN if action!=1206)
    for view in (11,12,13,14,15,19):
        operations.update((action,label) for label,action in PAGES[view][1])
    favorites='set title="主菜单 — 收藏的常用功能"\nif view == 42 then\nset title="主菜单 — 点选收藏／取消收藏"\nendif\n'
    for action,label in operations.items():
        favorites+=f'''if view == 42 or GetStoredInteger(hke_ExData,"opfav"+I2S(p),"{action}") > 0 then
set n={action}
set label={quoted(label)}
if view == 42 then
set n=n+1000000
if GetStoredInteger(hke_ExData,"opfav"+I2S(p),"{action}") > 0 then
set label="★ "+label
else
set label="☆ "+label
endif
endif
call hke_ExRow(p,total,label,n,0)
set total=total+1
endif
'''
    # Data initializers are separated into timer-sized chunks. Cache keys avoid
    # the classic 8192-array limit for maps with many custom objects.
    statements = []
    for kind, rows in enumerate(grouped):
        for n, row in enumerate(rows, 1):
            description=row.get('description') or '当前地图未提供说明。'
            if _label(row['name'])!=row['name']:
                description='完整名称：'+row['name']+'\n'+description
            parts = _fragments(description)
            store = f'call StoreInteger(hke_ExData,"{kind}","{n}i",\'{row["rawcode"]}\')\n'
            store += f'call StoreInteger(hke_ExData,"id{kind}",I2S(\'{row["rawcode"]}\'),{n})\n'
            store += f'call StoreInteger(hke_ExData,"code{kind}",{quoted(row["rawcode"])},{n})\n'
            for key, value in [('c', row['rawcode']), ('n', _label(row['name']))] + [(f'd{i}', part) for i, part in enumerate(parts)]:
                store += f'call StoreString(hke_ExData,"{kind}","{n}{key}",{quoted(value)})\n'
            for key, value in [('l', row['maxLevel']), ('d', len(parts)), ('m', int(row['custom'])),
                               ('p', int(row['powerup'])), ('q', row['charges']), ('r', int(row['droppable'])), ('u', int(row['unsafe']))]:
                store += f'call StoreInteger(hke_ExData,"{kind}","{n}{key}",{value})\n'
            statements.append(store)
    chunks = [statements[i:i+32] for i in range(0, len(statements), 32)]
    init = f'set hke_ExBlocks={len(chunks)+1}\n'
    for kind, rows in enumerate(grouped):
        init += f'set hke_ExCount[{kind}]={len(rows)}\n'
    mines = known.get('gold_mines', ['Agld', 'Abgm'])
    init += f'set hke_ExCount[8]={len(mines)}\n'
    for n, code in enumerate(mines):
        init += f'call StoreInteger(hke_ExData,"gold","{n}",\'{code}\')\n'
    for n, name in enumerate(('物品目录', '技能目录', '单位召唤目录', '科技研究目录')):
        init += f'call StoreString(hke_ExData,"9","{n}n",{quoted(name)})\n'
    for n, name in enumerate(('回血', '回魔', '清冷却')):
        init += f'call StoreString(hke_ExData,"9","{n}a",{quoted(name)})\n'
    for action,label in operations.items():
        init+=f'call StoreString(hke_ExData,"oplabels","{action}",{quoted(label)})\n'
    functions += 'function hke_Ids0 takes nothing returns nothing\n'+init+'endfunction\n'
    for n, chunk in enumerate(chunks, 1):
        functions += f'function hke_Ids{n} takes nothing returns nothing\n'+''.join(chunk)+'endfunction\n'
    replacements = {'__CLEAR_ORIGINAL__': clear, '__MAIN__': main, '__DETAIL__': detail,
                    '__PAGES__': page_code, '__SLOT__': slot, '__ARTIFACTS__': artifacts,'__FAVORITES__':favorites}
    for key, value in replacements.items():
        functions = functions.replace(key, value)
    return globals_code, functions
