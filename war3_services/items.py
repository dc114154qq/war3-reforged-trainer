"""items operations; transport and lifecycle belong to GameSession."""
from war3_selection_protocol import SIGNATURES

class ItemsService:
    def item_abilities(self,unit,item,*,native_target,native_item,slot=0,action=0,ability_rawcode=0):
        from war3_item_ability_protocol import SIGNATURES as ITEM_ABILITIES,build_work,decode_work
        from war3_game_session import UnitRef,ItemRef
        if type(unit) is not UnitRef or type(item) is not ItemRef:
            raise TypeError('Item ability operation requires typed UnitRef and ItemRef')
        def builder(entries,tls):
            with self.memory_factory(self.pid) as memory:
                registry,_,_=self.session.prepare(memory)
                self.session.resolve(memory,registry,unit);self.session.resolve(memory,registry,item)
            return build_work(entries,tls,target=native_target,item=native_item,base=registry.base,
                unit_full=unit.handle.value,item_full=item.handle.value,rawcode=item.rawcode,
                slot=slot,action=action,ability_rawcode=ability_rawcode)
        return self._execute('item_ability',tuple(n for n,_ in SIGNATURES+ITEM_ABILITIES),
            builder,decode_work,dict(action=action,target=native_target,item=native_item,
                slot=slot,ability_rawcode=ability_rawcode))

    def item_batch(self,action=0,rawcode=0,charges=-1,target_unit_rawcode=0,target_unit=0,expected_item=0,creation_route=0):
        from war3_item_protocol import SIGNATURES as ITEMS,build_work as build,decode_work as decode
        if any(isinstance(v,bool) or not isinstance(v,int) for v in (action,rawcode,charges,target_unit_rawcode,target_unit,expected_item,creation_route)):
            raise ValueError('Item arguments must be integers')
        if (action not in (0,1,2,3,4,5,6,7) or not 0<=rawcode<=0xffffffff or (action in (1,3,7) and not rawcode)
            or (action in (0,2,4,5,6) and rawcode) or not -1<=charges<=1000000000
            or (action in (2,3) and charges<1) or (action in (0,1,4,5,6) and charges!=-1)
            or (action==7 and not 0<=charges<6) or not 0<=target_unit_rawcode<=0xffffffff
            or (target_unit_rawcode and action!=7) or not 0<=target_unit<=0xffffffffffffffff
            or not 0<=expected_item<=0xffffffffffffffff or ((target_unit or expected_item) and action!=7)
            or creation_route not in (0,1) or creation_route and action!=7):
            raise ValueError('Invalid item operation')
        from war3_item_protocol import required_signatures
        names=tuple(n for n,_ in SIGNATURES)+tuple(n for n,_ in required_signatures(action,creation_route))
        return self._execute('item',names,lambda entries,tls:build(entries,tls,action,rawcode,charges,target_unit_rawcode,target_unit,expected_item,creation_route),decode,
                             dict(action=action,rawcode=rawcode,charges=charges,target_unit_rawcode=target_unit_rawcode,target_unit=target_unit,expected_item=expected_item,creation_route=creation_route))


    def item_catalog(self, action=1, limit=0, x_bits=0, y_bits=0,
                     handles=(), rawcodes=(), dry_run=False):
        from war3_item_catalog_protocol import (
            ACTION_CREATE, ACTION_REMOVE, ACTION_CREATE_LIST,
            SIGNATURES as CATALOG_SIGNATURES,
            build_work as build, decode_work as decode, required_signatures,
        )
        if isinstance(action, bool) or action not in (ACTION_CREATE, ACTION_REMOVE, ACTION_CREATE_LIST):
            raise ValueError('Invalid item catalog action')
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 100000:
            raise ValueError('Invalid item catalog limit')
        handles = tuple(int(handle) for handle in handles)
        rawcodes = tuple(int(rawcode) for rawcode in rawcodes)
        names = tuple(name for name, _signature in required_signatures(action))
        result = self._execute(
            'item_catalog',
            names,
            lambda entries, tls: build(
                {name: entries[name] for name, _signature in CATALOG_SIGNATURES
                 if name in entries},
                tls,
                action=action,
                limit=limit,
                x_bits=x_bits,
                y_bits=y_bits,
                handles=handles,
                rawcodes=rawcodes,
                dry_run=dry_run,
            ),
            decode,
            dict(action=action,limit=limit,handle_count=len(handles),rawcode_count=len(rawcodes),dry_run=dry_run),
        )
        return result


    def item_field_batch(self, slot, action, fields, target_unit=0):
        from war3_item_field_protocol import (
            SIGNATURES as FIELD_SIGNATURES,
            build_work as build,
            decode_work as decode,
        )
        if (isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < 6
                or isinstance(action, bool) or action not in (0, 1)
                or isinstance(target_unit, bool) or not isinstance(target_unit, int)
                or not 0 <= target_unit <= 0xFFFFFFFFFFFFFFFF):
            raise ValueError('Invalid current-engine item field operation')
        names = tuple(n for n, _ in SIGNATURES + FIELD_SIGNATURES)
        return self._execute(
            'item_field',
            names,
            lambda entries, tls: build(entries, tls, slot, action, fields, target_unit),
            decode,
            dict(slot=slot, action=action, field_count=len(fields), target_unit=target_unit),
        )
