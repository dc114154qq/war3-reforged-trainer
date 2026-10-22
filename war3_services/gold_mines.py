"""Mine resources through the session's existing native execution backend."""
import re
from war3_gold_mine_protocol import MAX_AMOUNT, SIGNATURES, SELECTION, build_work, decode_work

def parse_amount(text):
    if isinstance(text,bool) or not re.fullmatch(r'[0-9]+',str(text).strip()):
        raise ValueError('金矿剩余金币请输入整数')
    value=int(str(text).strip())
    if not 0<=value<=MAX_AMOUNT:raise ValueError(f'金矿剩余金币范围为 0 到 {MAX_AMOUNT}')
    return value

def execute(host, scope='selected', amount=None):
    if scope not in ('selected','world'):raise ValueError('请选择选中金矿或全图金矿')
    action=0 if amount is None else 1
    target=0 if amount is None else parse_amount(amount)
    engine=host._engine_instance_24268()
    return engine._execute('gold_mine',tuple(n for n,_ in SELECTION+SIGNATURES),
        lambda entries,tls:build_work(entries,tls,action,int(scope=='world'),target),decode_work,
        dict(action=action,scope=scope,target=target))
