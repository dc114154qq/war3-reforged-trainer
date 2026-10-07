"""units operations; transport and lifecycle belong to GameSession."""
from war3_selection_protocol import SIGNATURES
from war3_hero_protocol import SIGNATURES as HERO_SIGNATURES, build_work, decode_work

class UnitsService:
    def hero_progress(self,target=0):
        if isinstance(target,bool) or not isinstance(target,int) or not 0<=target<=100000:
            raise ValueError('Hero level must be integer 1..100000; 0 means read-only query')
        names=tuple(n for n,_ in SIGNATURES)+tuple(n for n,_ in HERO_SIGNATURES)
        return self._execute('hero',names,lambda entries,tls:build_work(entries,tls,target),decode_work,dict(target=target))


    def hero_attributes(self, target=None):
        from war3_hero_attributes_protocol import (
            SIGNATURES as ATTRIBUTE_SIGNATURES,
            build_work as build,
            decode_work as decode,
        )
        if target is not None:
            values = (target,) * 3 if isinstance(target, int) and not isinstance(target, bool) else tuple(target)
            if len(values) != 3 or any(
                isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000_000
                for value in values
            ):
                raise ValueError('Hero attributes must contain three integers in 0..1000000000')
        names = tuple(name for name, _signature in SIGNATURES + ATTRIBUTE_SIGNATURES)
        return self._execute(
            'hero_attributes', names,
            lambda entries, tls: build(entries, tls, target),
            decode,
            dict(target=target),
        )


    def attack_speed(self, unit_object, attack, full_handle,
                     rawcode, target_aps=0.0, weapon=0):
        from war3_attack_speed_protocol import (
            SIGNATURES as ATTACK_SPEED_SIGNATURES,
            build_work as build,
            decode_work as decode,
        )
        values = (unit_object, attack, full_handle, rawcode, weapon)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError('Attack-speed identities must be integers')
        if not all(values[:4]) or weapon not in (0, 1):
            raise ValueError('Invalid attack-speed identity')
        target_aps = float(target_aps)
        if not 0.0 <= target_aps <= 1000.0:
            raise ValueError('True attack speed must be in 0..1000 attacks per second')
        names = tuple(name for name, _signature in SIGNATURES + ATTACK_SPEED_SIGNATURES)
        return self._execute(
            'attack_speed', names,
            lambda entries, tls: build(
                entries, tls, unit_object, attack, full_handle,
                rawcode, self._attack_speed_module_base, target_aps, weapon,
            ),
            decode,
            dict(unit_object=unit_object, attack=attack, full_handle=full_handle,
                 rawcode=rawcode, target_aps=target_aps, weapon=weapon),
        )


    def bind_unit_refs(self, refs, strict_selection=True):
        """Resolve exact external identities into the Native handle namespace."""
        from war3_game_session import FullHandle, ObjectAddress, UnitRef
        if type(strict_selection) is not bool:
            raise TypeError('Unit binding selection mode must be boolean')
        if type(refs) is not tuple or not 1 <= len(refs) <= 24:
            raise ValueError('Unit binding requires a tuple of 1..24 UnitRef objects')
        if any(type(ref) is not UnitRef or type(ref.handle) is not FullHandle
               or type(ref.address) is not ObjectAddress for ref in refs):
            raise TypeError('Unit binding requires UnitRef with full handles and object addresses')
        if (len({ref.handle.value for ref in refs}) != len(refs)
                or len({ref.address.value for ref in refs}) != len(refs)):
            raise ValueError('Unit binding contains duplicate object identities')
        if any((ref.session, ref.epoch) != (refs[0].session, refs[0].epoch) for ref in refs):
            raise ValueError('Unit binding sources belong to different sessions or epochs')
        from war3_unit_bindings_protocol import build_work as build, decode_work as decode

        def builder(entries, tls):
            with self.memory_factory(self.pid) as memory:
                registry, _, _ = self.session.prepare(memory)
                for ref in refs:
                    self.session.resolve(memory, registry, ref)
                resolver_rva = self.session.profile.section('addresses')['unit_resolver']
                if not resolver_rva:
                    raise ValueError('Unit binding resolver has not been adapted')
                return build(entries, tls, base=registry.base,
                             unit_resolver=registry.base + resolver_rva,
                             refs=refs, strict_selection=strict_selection)

        def decoder(payload,count):
            bindings=decode(payload,count,expected_sources=refs)
            with self.memory_factory(self.pid) as memory:
                registry,_,_=self.session.prepare(memory)
                for ref in refs:self.session.resolve(memory,registry,ref)
            return bindings

        return self._execute(
            'unit_bindings', tuple(name for name, _ in SIGNATURES), builder,
            decoder,
            dict(strict_selection=strict_selection, expected_count=len(refs),
                 sources=tuple(dict(full_handle=ref.handle.value,
                                    object_address=ref.address.value, rawcode=ref.rawcode)
                               for ref in refs)),
        )


    def clone_batch(self, *, keep=False, preserve_owner=False,
                    copy_abilities=True, copy_items=True,
                    spawn=False, spawn_x_bits=0, spawn_y_bits=0,
                    expected_sources=None):
        from war3_clone_protocol import (
            SIGNATURES as CLONE_SIGNATURES,
            CLONE_COPY_ABILITIES, CLONE_COPY_ITEMS, CLONE_KEEP,
            CLONE_PRESERVE_OWNER, CLONE_USE_SPAWN,
            build_work as build, decode_work as decode,
        )
        flags = 0
        if keep: flags |= CLONE_KEEP
        if preserve_owner: flags |= CLONE_PRESERVE_OWNER
        if copy_abilities: flags |= CLONE_COPY_ABILITIES
        if copy_items: flags |= CLONE_COPY_ITEMS
        if spawn: flags |= CLONE_USE_SPAWN
        names = tuple(n for n, _ in SIGNATURES + CLONE_SIGNATURES)
        request = dict(keep=keep, preserve_owner=preserve_owner,
                       copy_abilities=copy_abilities, copy_items=copy_items,
                       spawn=spawn, spawn_x_bits=spawn_x_bits, spawn_y_bits=spawn_y_bits)
        if expected_sources is None:
            return self._execute(
                'clone', names,
                lambda entries, tls: build(entries, tls, flags=flags,
                                           spawn_x_bits=spawn_x_bits,
                                           spawn_y_bits=spawn_y_bits),
                decode, request,
            )
        from war3_clone_bound_protocol import (
            build_work as build_bound, decode_work as decode_bound,
            validate_expected_sources,
        )
        validate_expected_sources(expected_sources)
        request['expected_sources'] = tuple(dict(
            native_handle=native.value, full_handle=ref.handle.value,
            object_address=ref.address.value, rawcode=ref.rawcode,
        ) for native, ref in expected_sources)

        def builder(entries, tls):
            # Reopen and verify the process/map and every original object on
            # each iteration. Never rebuild the bindings from current selection.
            with self.memory_factory(self.pid) as memory:
                registry, _, _ = self.session.prepare(memory)
                self.session.require_write()
                for _, ref in expected_sources:
                    self.session.resolve(memory, registry, ref)
                resolver_rva = self.session.profile.section('addresses')['unit_resolver']
                if not resolver_rva:
                    raise ValueError('Bound clone unit resolver has not been adapted')
                return build_bound(
                    entries, tls, base=registry.base,
                    unit_resolver=registry.base + resolver_rva,
                    expected_sources=expected_sources, flags=flags,
                    spawn_x_bits=spawn_x_bits, spawn_y_bits=spawn_y_bits,
                )

        return self._execute(
            'clone_bound', names, builder,
            lambda payload, count: decode_bound(payload, count, expected_sources=expected_sources),
            request,
        )


    def unit_action_batch(self, action, *, value=0, x_bits=0, y_bits=0,
                          scale_x_bits=0, scale_y_bits=0, scale_z_bits=0):
        from war3_unit_action_protocol import (
            ACTION_SIGNATURES, build_work as build, decode_work as decode,
        )
        if not isinstance(action, int) or isinstance(action, bool):
            raise ValueError('Invalid current-engine unit action')
        names = tuple(n for n, _ in SIGNATURES + ACTION_SIGNATURES)
        return self._execute(
            'unit_action', names,
            lambda entries, tls: build(
                entries, tls, action, value=value, x_bits=x_bits, y_bits=y_bits,
                scale_x_bits=scale_x_bits, scale_y_bits=scale_y_bits,
                scale_z_bits=scale_z_bits,
            ),
            decode,
            dict(action=action, value=value, x_bits=x_bits, y_bits=y_bits,
                 scale_x_bits=scale_x_bits, scale_y_bits=scale_y_bits,
                 scale_z_bits=scale_z_bits),
        )


    def unit_stats(self, action=0, value=0, target_unit=0):
        from war3_unit_stats_protocol import (
            SIGNATURES as UNIT_STATS_SIGNATURES,
            build_work as build,
            decode_work as decode,
        )
        names = tuple(name for name, _signature in SIGNATURES + UNIT_STATS_SIGNATURES)
        return self._execute(
            'unit_stats', names,
            lambda entries, tls: build(entries, tls, int(action), value, int(target_unit)),
            decode,
            dict(action=int(action), value=value, target_unit=int(target_unit)),
        )


    def position_batch(self, x_bits, y_bits):
        from war3_position_protocol import SIGNATURES as POSITION_SIGNATURES, build_work as build, decode_work as decode
        if (isinstance(x_bits, bool) or not isinstance(x_bits, int)
                or isinstance(y_bits, bool) or not isinstance(y_bits, int)):
            raise ValueError('Position bits must be integers')
        names = tuple(n for n, _ in SIGNATURES + POSITION_SIGNATURES)
        return self._execute(
            'position', names,
            lambda entries, tls: build(entries, tls, x_bits, y_bits),
            decode,
            dict(x_bits=x_bits, y_bits=y_bits),
        )


    def position_target_batch(self, target_unit, x_bits, y_bits):
        from war3_position_target_protocol import (
            SIGNATURES as POSITION_SIGNATURES,
            build_work as build,
            decode_work as decode,
        )
        if (isinstance(target_unit, bool) or not isinstance(target_unit, int)
                or not 0 < target_unit <= 0xFFFFFFFFFFFFFFFF
                or isinstance(x_bits, bool) or not isinstance(x_bits, int)
                or isinstance(y_bits, bool) or not isinstance(y_bits, int)):
            raise ValueError('Invalid targeted position operation')
        names = tuple(n for n, _ in SIGNATURES + POSITION_SIGNATURES)
        return self._execute(
            'position_target', names,
            lambda entries, tls: build(entries, tls, target_unit, x_bits, y_bits),
            decode,
            dict(target_unit=target_unit, x_bits=x_bits, y_bits=y_bits),
        )


    def spawn_batch(self, rawcode, x_bits=0, y_bits=0, facing_bits=0):
        from war3_spawn_protocol import SIGNATURES as SPAWN_SIGNATURES, build_work as build, decode_work as decode
        values = (rawcode, x_bits, y_bits, facing_bits)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError('Spawn arguments must be integers')
        if not 0 < rawcode <= 0xFFFFFFFF or any(not 0 <= value <= 0xFFFFFFFF for value in values[1:]):
            raise ValueError('Invalid current-engine spawn operation')
        names = tuple(n for n, _ in SPAWN_SIGNATURES)
        return self._execute(
            'spawn', names,
            lambda entries, tls: build(entries, tls, rawcode, x_bits, y_bits, facing_bits),
            decode,
            dict(rawcode=rawcode, x_bits=x_bits, y_bits=y_bits, facing_bits=facing_bits),
        )
