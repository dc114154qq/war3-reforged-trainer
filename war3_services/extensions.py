"""extensions operations; transport and lifecycle belong to GameSession."""
from war3_selection_protocol import SIGNATURES

class ExtensionsService:
    def equipment(self,rawcode=0,action=0,target_unit=0,created=0,replaced=0):
        from war3_equipment_protocol import SIGNATURES as EQ,build_work as build,decode_work as decode
        return self._execute('equipment',tuple(n for n,_ in SIGNATURES+EQ),
            lambda entries,tls:build(entries,tls,rawcode,action,target_unit,created,replaced),decode,
            dict(rawcode=rawcode,action=action,target_unit=target_unit,created=created,replaced=replaced))


    def extension(self,ability_rawcodes=(),action=0,target_unit=0,slot=0,item_rawcode=0,item_handle=0,resolver=0):
        from war3_extension_protocol import SIGNATURES as EXT,build_work as build,decode_work as decode
        values=tuple(int(value) for value in ability_rawcodes)
        return self._execute('extension',tuple(n for n,_ in SIGNATURES+EXT),
            lambda entries,tls:build(entries,tls,values,action,target_unit,slot,item_rawcode,item_handle,
                                     resolver=(resolver or getattr(self,'_extension_resolver',0))),decode,
            dict(action=action,target_unit=target_unit,slot=slot,item_rawcode=item_rawcode,
                 item_handle=item_handle,ability_count=len(values)))


    def talent_order(self,target,controller,order,choice):
        from war3_talent_order_protocol import SIGNATURES as TALENT,build_work as build,decode_work as decode
        return self._execute('talent_order',tuple(n for n,_ in SIGNATURES+TALENT),
            lambda entries,tls:build(entries,tls,target,controller,order,choice),decode,
            dict(target=target,controller=controller,order=order,choice=choice))


    def stat_details(self,action=0,stat_index=0,target=0.0,controller=0,target_unit=0,target_full_handle=0):
        from war3_stat_details_protocol import SIGNATURES as STATS,build_work as build,decode_work as decode
        return self._execute('stat_details',tuple(n for n,_ in SIGNATURES+STATS),
            lambda entries,tls:build(entries,tls,action,stat_index,target,controller,target_unit,
                                     target_full_handle,self._stat_resolver_base if target_full_handle else 0),decode,
            dict(action=action,stat_index=stat_index,target=target,controller=controller,target_unit=target_unit,
                 target_full_handle=target_full_handle))
