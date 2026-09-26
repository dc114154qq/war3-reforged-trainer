"""abilities operations; transport and lifecycle belong to GameSession."""
from war3_selection_protocol import SIGNATURES

class AbilitiesService:
    def ability_batch(self,rawcode,action=0,level=0,target_unit=0):
        from war3_ability_protocol import SIGNATURES as ABILITIES,build_work as build,decode_work as decode
        if (isinstance(rawcode,bool) or not isinstance(rawcode,int) or not 0<rawcode<=0xffffffff
            or isinstance(action,bool) or not isinstance(action,int) or action not in range(6)
            or isinstance(level,bool) or not isinstance(level,int) or not 0<=level<=100000
            or (action in (3,4) and not level) or (action in (0,2,5) and level)):
            raise ValueError('Invalid current-engine ability operation')
        names=tuple(n for n,_ in SIGNATURES+ABILITIES)
        return self._execute('ability',names,lambda entries,tls:build(entries,tls,rawcode,action,level,target_unit),decode,
                             dict(rawcode=rawcode,action=action,level=level,target_unit=target_unit))


    def ability_field_batch(self, rawcode, level, action, fields, target_unit=0):
        from war3_ability_field_protocol import (
            SIGNATURES as FIELD_SIGNATURES,
            build_work as build,
            decode_work as decode,
        )
        if (isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 < rawcode <= 0xFFFFFFFF
                or isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 1000
                or isinstance(action, bool) or action not in (0, 1)
                or isinstance(target_unit, bool) or not isinstance(target_unit, int)
                or not 0 <= target_unit <= 0xFFFFFFFFFFFFFFFF):
            raise ValueError('Invalid current-engine ability field operation')
        names = tuple(n for n, _ in SIGNATURES + FIELD_SIGNATURES)
        return self._execute(
            'ability_field',
            names,
            lambda entries, tls: build(
                entries, tls, rawcode, level, action, fields, target_unit,
            ),
            decode,
            dict(rawcode=rawcode, level=level, action=action,
                 field_count=len(fields), target_unit=target_unit),
        )


    def effect_batch(self, rawcode, action, x_bits=0, y_bits=0, *, area_bits=0, passes=1):
        from war3_effect_protocol import SIGNATURES as EFFECT_SIGNATURES, build_work as build, decode_work as decode
        if (isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 < rawcode <= 0xFFFFFFFF
                or isinstance(action, bool) or action not in range(1, 5)
                or any(isinstance(value, bool) or not isinstance(value, int)
                       for value in (x_bits, y_bits, area_bits, passes))
                or not 0 <= area_bits <= 0xFFFFFFFF or not 1 <= passes <= 255):
            raise ValueError('Invalid current-engine effect operation')
        wire_x = x_bits if action == 3 else area_bits
        wire_y = y_bits if action == 3 else passes
        names = tuple(n for n, _ in SIGNATURES + EFFECT_SIGNATURES)
        return self._execute(
            'effect', names,
            lambda entries, tls: build(
                entries, tls, rawcode, action, wire_x, wire_y, area_bits,
                resolver=self._effect_resolver,
                unit_map=self._effect_unit_map,
            ),
            decode,
            dict(rawcode=rawcode, action=action, x_bits=x_bits, y_bits=y_bits,
                 area_bits=area_bits, passes=passes),
        )


    def world_effect_batch(self, rawcode, action, success_limit=0):
        from war3_world_effect_protocol import (
            SIGNATURES as WORLD_EFFECT_SIGNATURES,
            build_work as build,
            decode_work as decode,
        )
        if (isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 < rawcode <= 0xFFFFFFFF
                or isinstance(action, bool) or action not in (1, 2, 3)
                or isinstance(success_limit, bool) or not 0 <= success_limit <= 65535):
            raise ValueError('Invalid current-engine world effect operation')
        names = tuple(n for n, _ in WORLD_EFFECT_SIGNATURES)
        return self._execute(
            'world_effect', names,
            lambda entries, tls: build(
                entries, tls, rawcode, action, success_limit,
                resolver=self._effect_resolver,
            ),
            decode,
            dict(rawcode=rawcode, action=action, success_limit=success_limit),
        )


    def world_cast(self, rawcode, action, *, order_id=0, cast_kind=1, area=0.0,
                   source=0, ability_handle=0, target=0, prior_area=0, added=0):
        from war3_world_cast_protocol import (
            SIGNATURES as CAST_SIGNATURES, build_work, decode_work,
        )
        from war3_selection_protocol import SIGNATURES as SELECTION_SIGNATURES
        names = tuple(name for name, _ in SELECTION_SIGNATURES + CAST_SIGNATURES)
        return self._execute(
            'world_cast', names,
            lambda entries, tls: build_work(
                entries, tls, action=action, rawcode=rawcode,
                order_id=order_id, cast_kind=cast_kind, area=area, source=source,
                ability_handle=ability_handle, target=target,
                prior_area=prior_area, added=added,
            ),
            decode_work,
            dict(action=action, rawcode=rawcode, order_id=order_id,
                 cast_kind=cast_kind, area=area, source=source,
                 ability_handle=ability_handle, target=target,
                 prior_area=prior_area, added=added),
        )
