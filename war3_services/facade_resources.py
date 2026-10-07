"""resources compatibility API; host primitives are explicitly bound once at composition."""
from __future__ import annotations
from contextlib import contextmanager

class ResourcesFacade:
    def _iter_resource_properties(
        self,
        pm: ProcessMemory,
        tag_addresses: Iterable[int] | None = None,
    ) -> Iterable[ResourceProperty]:
        from war3_game_profile import current_profile
        return current_profile().adapter.legacy._iter_resource_properties(self, pm, tag_addresses)


    @staticmethod
    def _resource_food_cap(
        used_prop: ResourceProperty | None,
        cap_prop: ResourceProperty | None,
        limit_prop: ResourceProperty | None,
    ) -> tuple[ResourceProperty | None, ResourceProperty | None]:
        del used_prop
        return cap_prop, limit_prop


    def _resource_cache_candidates_from_group(
        self,
        group: dict[int, ResourceProperty],
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> list[tuple[int, ResourceCache]]:
        candidates: list[tuple[int, ResourceCache]] = []
        for start_kind in sorted({kind - 2 for kind in group}):
            header_prop = group.get(start_kind)
            player_prop = group.get(start_kind + 1)
            if header_prop is None or player_prop is None:
                continue
            if not 0 <= header_prop.value <= 32 or not 0 <= player_prop.value <= 16:
                continue
            gold_prop = group.get(start_kind + 2)
            lumber_prop = group.get(start_kind + 3)
            if gold_prop is None or lumber_prop is None:
                continue
            gold = gold_prop.value // 10
            lumber = lumber_prop.value // 10
            if not 0 <= gold <= 10_000_000 or not 0 <= lumber <= 10_000_000:
                continue
            if current_gold is not None and gold != int(current_gold):
                continue
            if current_lumber is not None and lumber != int(current_lumber):
                continue

            cap_prop = group.get(start_kind + 5)
            used_prop = group.get(start_kind + 6)
            limit_prop = group.get(start_kind + 7)
            cap_choice, limit_choice = self._resource_food_cap(used_prop, cap_prop, limit_prop)
            food_used = used_prop.value if used_prop is not None else 0
            food_cap = cap_choice.value if cap_choice is not None else 0
            food_limit = limit_choice.value if isinstance(limit_choice, ResourceProperty) else 0
            if current_food is not None and food_used != int(current_food):
                continue
            if current_food_cap is not None and food_cap != int(current_food_cap):
                continue

            score = 100
            if current_gold is not None:
                score += 10_000
            if current_lumber is not None:
                score += 10_000
            if current_food is not None:
                score += 5_000
            if current_food_cap is not None:
                score += 5_000
            if gold > 0:
                score += 80
            else:
                score -= 50
            if lumber > 0:
                score += 80
            else:
                score -= 50
            if gold > 0 and lumber > 0:
                score += 140
            if used_prop is not None and cap_choice is not None and 0 <= food_used <= food_cap <= 1000 and food_cap > 0:
                score += 500
            elif current_food is None and current_food_cap is None:
                score -= 180
            if cap_prop is not None:
                score += 80
            if limit_prop is not None:
                score += 40
            score += min(gold + lumber, 20_000) // 200

            cache = ResourceCache(
                gold_prop.address,
                lumber_prop.address,
                gold,
                lumber,
                used_prop.address if used_prop is not None else 0,
                cap_choice.address if cap_choice is not None else 0,
                limit_choice.address if isinstance(limit_choice, ResourceProperty) else 0,
                food_used,
                food_cap,
                food_limit,
                start_kind,
                f"prop^glf owner=0x{gold_prop.owner_key:x} start_kind=0x{start_kind:x}",
                gold_prop.owner_key,
                header_prop.value,
                player_prop.value,
                score,
            )
            candidates.append((score, cache))
        return candidates


    def _resource_cache_from_group(
        self,
        group: dict[int, ResourceProperty],
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> tuple[int, ResourceCache] | None:
        best: tuple[int, ResourceCache] | None = None
        for candidate in self._resource_cache_candidates_from_group(
            group, current_gold, current_lumber, current_food, current_food_cap
        ):
            if best is None or candidate[0] > best[0]:
                best = candidate
        return best


    def _resource_property_groups(
        self,
        pm: ProcessMemory,
        warm_unit_owner_index: bool = False,
    ) -> dict[int, dict[int, ResourceProperty]]:
        resource_tag_addresses: Iterable[int] | None = None
        if warm_unit_owner_index:
            resource_tag = struct.pack("<Q", self.RESOURCE_PROP_TAG)
            unit_owner_tag = struct.pack("<Q", self.UNIT_OWNER_TAG)
            tag_hits = pm.scan_bytes_private_many(
                (resource_tag, unit_owner_tag),
                max_region_size=1024 * 1024,
            )
            resource_tag_addresses = tag_hits[resource_tag]
            self._unit_owner_index = self._unit_owner_index_from_tag_addresses(
                pm,
                tag_hits[unit_owner_tag],
            )
        groups: dict[int, dict[int, ResourceProperty]] = {}
        for prop in self._iter_resource_properties(pm, resource_tag_addresses):
            owner_group = groups.setdefault(prop.owner_key, {})
            current = owner_group.get(prop.kind)
            if current is None or prop.address > current.address:
                owner_group[prop.kind] = prop
        return groups


    def _resource_property_groups_win10(
        self,
        pm: ProcessMemory,
        warm_unit_owner_index: bool = False,
    ) -> dict[int, dict[int, ResourceProperty]]:
        resource_tag = struct.pack("<Q", self.RESOURCE_PROP_TAG)
        unit_owner_tag = struct.pack("<Q", self.UNIT_OWNER_TAG)
        patterns = (
            (resource_tag, unit_owner_tag)
            if warm_unit_owner_index
            else (resource_tag,)
        )
        tag_hits = self._scan_bytes_private_many_win10(
            pm,
            patterns,
            max_region_size=1024 * 1024,
        )
        needs_expand = (
            not tag_hits[resource_tag]
            or (warm_unit_owner_index and not tag_hits[unit_owner_tag])
        )
        if needs_expand:
            regions = getattr(pm, "regions", None)
            if callable(regions):
                regions(force_refresh=True)
            tag_hits = self._scan_bytes_private_many_win10(
                pm,
                patterns,
                max_region_size=64 * 1024 * 1024,
            )
        needs_expand = (
            not tag_hits[resource_tag]
            or (warm_unit_owner_index and not tag_hits[unit_owner_tag])
        )
        if needs_expand:
            tag_hits = self._scan_bytes_private_many_win10(
                pm,
                patterns,
                max_region_size=None,
            )
        if warm_unit_owner_index:
            self._unit_owner_index = self._unit_owner_index_from_tag_addresses(
                pm,
                tag_hits[unit_owner_tag],
            )
        groups: dict[int, dict[int, ResourceProperty]] = {}
        for prop in self._iter_resource_properties(pm, tag_hits[resource_tag]):
            owner_group = groups.setdefault(prop.owner_key, {})
            current = owner_group.get(prop.kind)
            if current is None or prop.address > current.address:
                owner_group[prop.kind] = prop
        return groups


    def _read_local_player_resources_via_native(self, pm: ProcessMemory) -> LocalPlayerResources:
        del pm
        handlers = self._discover_native_handlers(None, ("GetLocalPlayer", "GetPlayerId", "GetPlayerState"))
        get_local_player = handlers["GetLocalPlayer"].handler_address
        get_player_id = handlers["GetPlayerId"].handler_address
        get_player_state = handlers["GetPlayerState"].handler_address
        states = (0xFFFFFFFF, 1, 2, 5, 4)
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    state,
                    get_local_player,
                    get_player_id,
                    get_player_state,
                )
                for state in states
            ),
        )
        values = [self._native_result_i32(result.result) for result in results]
        snapshot = LocalPlayerResources(*values)
        if not 0 <= snapshot.player_id < 28:
            raise RuntimeError(f"GetPlayerId 返回异常玩家槽：{snapshot.player_id}")
        if not 0 <= snapshot.gold <= 10_000_000 or not 0 <= snapshot.lumber <= 10_000_000:
            raise RuntimeError("GetPlayerState 返回的金币/木材超出合理范围")
        if not 0 <= snapshot.food_used <= 10_000 or not 0 <= snapshot.food_cap <= 10_000:
            raise RuntimeError("GetPlayerState 返回的人口数值超出合理范围")
        return snapshot


    def _read_player_resources_via_native(self, player_id: int) -> LocalPlayerResources:
        cache = self._native_resource_cache_for_player(player_id)
        return LocalPlayerResources(cache.player_value, cache.gold, cache.lumber,
                                    cache.food_used, cache.food_cap)


    def _player_resource_query_ops(self, player_id: int, handlers: dict[str, NativeHandler]) -> tuple:
        if not 0 <= player_id < 28:
            raise ValueError("Player slot must be in 0..27")
        return tuple((self.NATIVE_HELPER_OP_JASS_PLAYER_STATE_QUERY, player_id,
                      handlers["Player"].handler_address, handlers["GetPlayerState"].handler_address, state)
                     for state in (1, 2, 5, 4, 6))


    def _decode_player_resource_cache(self, player_id: int, results: Iterable[NativeHelperOpResult]) -> ResourceCache | None:
        results = tuple(results)
        if (len(results) != 5 or any(r.kind != self.NATIVE_HELPER_OP_JASS_PLAYER_STATE_QUERY or r.last_error
                                     or r.result >> 32 not in (0, 1) for r in results)):
            raise RuntimeError("Incomplete native player resource snapshot")
        present = [r.result >> 32 for r in results]
        if not any(present):
            return None
        if not all(present):
            raise RuntimeError("Player disappeared during native resource read")
        gold, lumber, used, cap, ceiling = (self._native_result_i32(r.result) for r in results)
        return ResourceCache(0, 0, gold, lumber, food_used=used, food_cap=cap, food_limit=ceiling,
                             block_start_kind=1 + player_id * 0x28,
                             source="persistent native player state", player_value=player_id)


    def _native_resource_cache(self, pm: ProcessMemory) -> ResourceCache:
        snapshot = self._read_local_player_resources_via_native(pm)
        return ResourceCache(
            0, 0, snapshot.gold, snapshot.lumber,
            food_used=snapshot.food_used,
            food_cap=snapshot.food_cap,
            block_start_kind=1 + snapshot.player_id * 0x28,
            source="persistent native player state",
            player_value=snapshot.player_id,
        )


    def _native_resource_cache_for_player(self, player_id: int) -> ResourceCache:
        handlers = self._query_native_table_handlers(("Player", "GetPlayerState"))
        ops = self._player_resource_query_ops(player_id, handlers)
        cache = self._decode_player_resource_cache(player_id, self._run_native_helper_ops(0, ops))
        if cache is None:
            raise RuntimeError(f"Native player slot {player_id} is unavailable")
        return cache


    def _set_local_player_state_via_native(
        self, pm: ProcessMemory, state: int, value: int,
    ) -> None:
        del pm
        handlers = self._discover_native_handlers(None, ("GetLocalPlayer", "SetPlayerState"))
        result = self._run_native_helper_ops(0, ((
            self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_SET,
            int(state),
            handlers["GetLocalPlayer"].handler_address,
            handlers["SetPlayerState"].handler_address,
            int(value),
        ),))[0]
        if result.last_error:
            raise RuntimeError(f"SetPlayerState native 写入失败：{result.last_error}")


    def _set_local_player_food_cap_via_native(self, pm: ProcessMemory, target_food_cap: int) -> None:
        del pm
        handlers = self._discover_native_handlers(
            None,
            ("GetLocalPlayer", "GetPlayerId", "GetPlayerState", "SetPlayerState"),
        )
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_SET,
                    4,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["SetPlayerState"].handler_address,
                    int(target_food_cap),
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    4,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["GetPlayerId"].handler_address,
                    handlers["GetPlayerState"].handler_address,
                ),
            ),
        )
        actual_food_cap = self._native_result_i32(results[1].result)
        if actual_food_cap != int(target_food_cap):
            raise RuntimeError(
                f"SetPlayerState 写入人口上限后读回 {actual_food_cap}，不是 {target_food_cap}"
            )


    def _set_local_player_food_used_via_native(self, pm: ProcessMemory, target_food_used: int) -> None:
        del pm
        handlers = self._discover_native_handlers(
            None,
            ("GetLocalPlayer", "GetPlayerId", "GetPlayerState", "SetPlayerState"),
        )
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_SET,
                    5,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["SetPlayerState"].handler_address,
                    int(target_food_used),
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    5,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["GetPlayerId"].handler_address,
                    handlers["GetPlayerState"].handler_address,
                ),
            ),
        )
        actual_food_used = self._native_result_i32(results[1].result)
        if actual_food_used != int(target_food_used):
            raise RuntimeError(
                f"SetPlayerState 写入当前人口后读回 {actual_food_used}，不是 {target_food_used}"
            )


    @staticmethod
    def _resource_cache_matches_local_snapshot(
        cache: ResourceCache,
        snapshot: LocalPlayerResources,
    ) -> bool:
        if cache.gold != snapshot.gold or cache.lumber != snapshot.lumber:
            return False
        if cache.food_used_address and cache.food_used != snapshot.food_used:
            return False
        if cache.food_cap_address and cache.food_cap != snapshot.food_cap:
            return False
        return True


    def validate_local_player_resource_cache(self, cache: ResourceCache) -> ResourceCache:
        if uses_indexed_backend(self):
            with self._process_memory() as memory:
                current = self._refresh_indexed_resource_cache(memory, cache)
                local = self._classic_local_resource_cache(memory)
                if (current.owner_key, current.player_handle) != (local.owner_key, local.player_handle):
                    raise RuntimeError("Resource cache is not the current local player")
                return current
        if cache.source != "persistent native player state":
            raise RuntimeError("历史资源地址缓存已禁用，请重新读取本地玩家 native 状态")
        current = self._native_resource_cache(None)
        if cache.player_value != current.player_value:
            raise RuntimeError("本地玩家 native 资源身份已经变化")
        return current


    def locate_local_player_resource_cache(self, caches: list[ResourceCache] | None = None) -> ResourceCache:
        if uses_indexed_backend(self):
            with self._process_memory() as memory:
                return self._classic_local_resource_cache(memory)
        # Local shortcuts target GetLocalPlayer, never the first row of the table.
        del caches
        return self._native_resource_cache(None)


    def _locate_local_player_resource_cache_with_pm(
        self,
        pm: ProcessMemory,
        caches: list[ResourceCache],
    ) -> ResourceCache | None:
        for _attempt in range(4):
            snapshot = self._read_local_player_resources_via_native(pm)
            expected_start_kind = 1 + snapshot.player_id * 0x28
            candidate_pool = list(caches)
            candidate_pool.extend(self._resource_candidates_by_start.get(expected_start_kind, ()))
            unique_pool = {
                (cache.gold_address, cache.lumber_address): cache
                for cache in candidate_pool
            }
            current_caches: list[ResourceCache] = []
            for cache in unique_pool.values():
                try:
                    current_caches.append(self._read_resource_cache_addresses(pm, cache))
                except (OSError, RuntimeError):
                    continue

            slot_matches = [
                cache
                for cache in current_caches
                if cache.block_start_kind == expected_start_kind
                and self._resource_cache_matches_local_snapshot(cache, snapshot)
            ]
            if len(slot_matches) == 1:
                match = slot_matches[0]
                self._remember_selection_player_from_resource_owner(
                    pm,
                    match.owner_key,
                    current_caches,
                )
                return replace(match, source=match.source + f" local_player={snapshot.player_id}")
        return None


    def list_resource_caches_win10(
        self,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> tuple[list[ResourceCache], ResourceCache]:
        # Compatibility name only: resource state is now read through the
        # injected native helper on every Windows version.
        caches = self.list_resource_caches(
            current_gold, current_lumber, current_food, current_food_cap,
        )
        return caches, self.locate_local_player_resource_cache(caches)


    def _resource_caches_from_groups(
        self,
        groups: dict[int, dict[int, ResourceProperty]],
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> list[ResourceCache]:
        candidates_by_start: dict[int, list[ResourceCache]] = {}
        found: list[ResourceCache] = []
        seen: set[tuple[int, int]] = set()
        for group in groups.values():
            candidates = self._resource_cache_candidates_from_group(
                group, current_gold, current_lumber, current_food, current_food_cap
            )
            if not candidates:
                continue
            for _candidate_score, candidate_cache in candidates:
                candidates_by_start.setdefault(candidate_cache.block_start_kind, []).append(candidate_cache)
            player_slot_candidates = [
                candidate
                for candidate in candidates
                if candidate[1].block_start_kind >= 1
                and (candidate[1].block_start_kind - 1) % 0x28 == 0
            ]
            if not player_slot_candidates:
                continue
            candidate = max(player_slot_candidates, key=lambda item: item[0])
            _score, cache = candidate
            key = (cache.gold_address, cache.lumber_address)
            if key in seen:
                continue
            seen.add(key)
            found.append(cache)
        self._resource_candidates_by_start = candidates_by_start
        return sorted(found, key=lambda cache: (cache.block_start_kind, cache.owner_key))


    def _classic_local_resource_cache(self, pm: ProcessMemory) -> ResourceCache:
        """Resolve the local player's resource properties on the 3.0 path."""
        from war3_object_registry import ObjectRegistry24268
        from war3_thread_context import GameThreadContext24268
        if self._classic_object_registry is None:
            self._classic_object_registry = ObjectRegistry24268.attach(pm)
        if self._classic_thread_context is None:
            self._classic_thread_context = GameThreadContext24268(
                pm, self._classic_object_registry.base, self.hwnd, self.pid)
        mode = self._classic_thread_context.read_mode(pm)
        player = self._classic_object_registry.local_player_for_mode(pm, mode.value)
        direct = self._indexed_resource_cache_for_player(pm, player)
        self._classic_resource_cache = direct
        return direct


    def _indexed_resource_cache_for_player(
        self, pm: ProcessMemory, player: int, player_id: int | None = None,
    ) -> ResourceCache:
        from war3_player_resources import SOURCE, read_player_properties
        from war3_game_profile import current_profile
        registry = self._classic_object_registry
        if player_id is None:
            player_id = registry.players(pm).index(player)
        session = getattr(self,"_game_session",None)
        if session is not None:
            from war3_external_backend import ExternalMemoryBackend
            owner, handle, states = ExternalMemoryBackend(session).read_player_properties(pm,registry,player,player_id)
        else:
            owner, handle, states = read_player_properties(pm, registry, player, player_id)
        gold_address, gold10 = states[1]
        lumber_address, lumber10 = states[2]
        cap_address, food_cap = states[4]
        used_address, food_used = states[5]
        limit_address, food_limit = states[6]
        if not 0 <= gold10 <= 100_000_000 or not 0 <= lumber10 <= 100_000_000:
            raise RuntimeError("Player resource values are outside supported bounds")
        return ResourceCache(
            gold_address, lumber_address, gold10 // 10, lumber10 // 10,
            food_used_address=used_address, food_cap_address=cap_address,
            food_limit_address=limit_address, food_used=food_used,
            food_cap=food_cap, food_limit=food_limit,
            block_start_kind=1 + current_profile().section("layouts")["property"]["state_identity_stride"] * player_id, source=SOURCE,
            owner_key=owner, player_value=player_id, score=1000,
            player_handle=handle, process_id=self.pid,
        )


    def _refresh_indexed_resource_cache(self, memory: ProcessMemory, cache: ResourceCache) -> ResourceCache:
        from war3_player_resources import SOURCE
        from war3_object_registry import ObjectRegistry24268
        if cache.source != SOURCE or cache.process_id != self.pid or cache.player_handle is None:
            raise RuntimeError("Resource cache belongs to another backend or process; reload resources")
        registry = self._classic_object_registry or ObjectRegistry24268.attach(memory)
        self._classic_object_registry = registry
        players = registry.players(memory)
        if not 0 <= cache.player_value < len(players):
            raise RuntimeError("Resource player slot is no longer available")
        current = self._indexed_resource_cache_for_player(memory, players[cache.player_value], cache.player_value)
        identity = ("owner_key", "player_handle", "gold_address", "lumber_address",
                    "food_used_address", "food_cap_address", "food_limit_address")
        if any(getattr(current, name) != getattr(cache, name) for name in identity):
            raise RuntimeError("Resource cache identity changed; reload resources")
        return current


    def list_resource_caches(
        self, current_gold: int | None = None, current_lumber: int | None = None,
        current_food: int | None = None, current_food_cap: int | None = None,
    ) -> list[ResourceCache]:
        if uses_indexed_backend(self):
            with self._process_memory() as memory:
                from war3_object_registry import ObjectRegistry24268
                registry = self._classic_object_registry or ObjectRegistry24268.attach(memory)
                self._classic_object_registry = registry
                direct_caches = [self._indexed_resource_cache_for_player(memory, player, slot)
                                 for slot, player in enumerate(registry.players(memory))]
                self._resource_candidates_by_start = {}
                return [cache for cache in direct_caches if all(
                    expected is None or actual == int(expected) for actual, expected in (
                        (cache.gold, current_gold), (cache.lumber, current_lumber),
                        (cache.food_used, current_food), (cache.food_cap, current_food_cap)))]
        try:
            handlers = self._query_native_table_handlers(("Player", "GetPlayerState"))
        except (TimeoutError, OSError) as exc:
            self._native_selection_unavailable = True
            self._native_fallback_reason = f"resource-list native timeout/failure: {exc}"
            return self.list_resource_caches(
                current_gold, current_lumber, current_food, current_food_cap
            )
        caches = []
        # Three complete players per command (15 ops); empty slots are explicit
        # results, while helper failures propagate instead of hiding whole rows.
        for start in range(0, 28, 3):
            players = tuple(range(start, min(start + 3, 28)))
            ops = tuple(op for player in players for op in self._player_resource_query_ops(player, handlers))
            results = self._run_native_helper_ops(0, ops)
            if len(results) != len(ops):
                raise RuntimeError("Incomplete native resource group list")
            for index, player in enumerate(players):
                cache = self._decode_player_resource_cache(player, results[index*5:(index+1)*5])
                if cache is not None and all(expected is None or actual == int(expected) for actual, expected in (
                    (cache.gold, current_gold), (cache.lumber, current_lumber),
                    (cache.food_used, current_food), (cache.food_cap, current_food_cap))):
                    caches.append(cache)
        return caches


    def _read_resource_cache_addresses(self, pm: ProcessMemory, cache: ResourceCache) -> ResourceCache:
        gold10 = pm.read_i32(cache.gold_address)
        lumber10 = pm.read_i32(cache.lumber_address)
        gold = gold10 // 10
        lumber = lumber10 // 10
        if not 0 <= gold <= 10_000_000 or not 0 <= lumber <= 10_000_000:
            raise RuntimeError("资源地址校验失败：金币/木材数值超出合理范围，请重新读取资源组")
        food_used = pm.read_i32(cache.food_used_address) if cache.food_used_address else 0
        food_cap = pm.read_i32(cache.food_cap_address) if cache.food_cap_address else 0
        food_limit = pm.read_i32(cache.food_limit_address) if cache.food_limit_address else 0
        return replace(cache, gold=gold, lumber=lumber, food_used=food_used, food_cap=food_cap, food_limit=food_limit)


    def read_resource_cache_addresses(self, cache: ResourceCache) -> ResourceCache:
        if uses_indexed_backend(self):
            with self._process_memory() as memory:
                return self._refresh_indexed_resource_cache(memory, cache)
        if cache.source not in ("persistent native player state", "3.0 indexed player properties"):
            raise RuntimeError("历史资源地址缓存已禁用，请重新读取本地玩家 native 状态")
        return self._native_resource_cache_for_player(cache.player_value)


    def write_resource_cache(
        self, cache: ResourceCache, target_gold: int | None = None,
        target_lumber: int | None = None, target_food_used: int | None = None,
        target_food_cap: int | None = None, sync_local_food_used: bool = False,
        sync_local_food_cap: bool = False,
    ) -> ResourceCache:
        del sync_local_food_used, sync_local_food_cap
        if uses_indexed_backend(self):
            targets = [(field, int(value), scale) for field, value, scale in (
                ("gold", target_gold, 10), ("lumber", target_lumber, 10),
                ("food_used", target_food_used, 1), ("food_cap", target_food_cap, 1),
            ) if value is not None]
            if not targets:
                raise ValueError("至少填写一个目标资源值")
            if any(not 0 <= value <= (10_000_000 if scale == 10 else 1000)
                   for _, value, scale in targets):
                raise ValueError("目标资源值超出允许范围")
            with self._process_memory(write=True) as memory:
                current = self._refresh_indexed_resource_cache(memory, cache)
                for field, value, scale in targets:
                    address = getattr(current, field + "_address")
                    memory.write_i32(address, value * scale)
                    if memory.read_i32(address) != value * scale:
                        raise RuntimeError("Player resource write acknowledgment differs from request")
                refreshed = self._refresh_indexed_resource_cache(memory, current)
            self._classic_resource_cache = refreshed
            return refreshed
        if cache.source not in ("persistent native player state", "3.0 indexed player properties"):
            raise RuntimeError("历史资源地址写入已禁用，请重新读取本地玩家 native 状态")
        targets = [(state, int(value)) for state, value in (
            (1, target_gold), (2, target_lumber), (5, target_food_used), (4, target_food_cap)) if value is not None]
        if not targets:
            raise ValueError("至少填写一个目标资源值")
        # Validate the complete request before submitting any mutation.
        if any(not 0 <= value <= (10_000_000 if state in (1, 2) else 1000) for state, value in targets):
            raise ValueError("目标资源值超出允许范围")
        handlers = self._query_native_table_handlers(("Player", "GetPlayerState", "SetPlayerState"))
        query = self._player_resource_query_ops(cache.player_value, handlers)
        setters = tuple((self.NATIVE_HELPER_OP_JASS_PLAYER_STATE_SET, cache.player_value,
                         handlers["Player"].handler_address, handlers["SetPlayerState"].handler_address,
                         (state << 32) | value) for state, value in targets)
        results = self._run_native_helper_ops(0, setters + query)
        if (len(results) != len(setters) + len(query) or any(r.last_error or r.kind != setters[i][0]
                or r.result != targets[i][1] for i, r in enumerate(results[:len(setters)]))):
            raise RuntimeError("Incomplete native resource write result")
        current = self._decode_player_resource_cache(cache.player_value, results[len(setters):])
        if current is None:
            raise RuntimeError("Native player disappeared after resource write")
        actual = {1: current.gold, 2: current.lumber, 5: current.food_used, 4: current.food_cap}
        for state, target in targets:
            if actual[state] != target:
                raise RuntimeError(f"native 资源写入读回不一致：state={state} expected={target} actual={actual[state]}")
        return current


    def locate_resource_cache(
        self,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
        pm: ProcessMemory | None = None,
    ) -> ResourceCache | None:
        if uses_indexed_backend(self):
            def matches(cache: ResourceCache) -> bool:
                return not any(
                    expected is not None and actual != int(expected)
                    for actual, expected in (
                        (cache.gold, current_gold),
                        (cache.lumber, current_lumber),
                        (cache.food_used, current_food),
                        (cache.food_cap, current_food_cap),
                    )
                )

            if pm is not None:
                cache = self._classic_local_resource_cache(pm)
                return cache if matches(cache) else None
            with self._process_memory() as memory:
                cache = self._classic_local_resource_cache(memory)
            return cache if matches(cache) else None

        # Legacy 1.0.19 keeps its native local-player shortcut.
        native = self._native_resource_cache(None)
        if (
            (current_gold is not None and native.gold != int(current_gold))
            or (current_lumber is not None and native.lumber != int(current_lumber))
            or (current_food is not None and native.food_used != int(current_food))
            or (current_food_cap is not None and native.food_cap != int(current_food_cap))
        ):
            return None
        return native


    def read_resource_cache(
        self,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> ResourceCache:
        if uses_indexed_backend(self):
            with self._process_memory() as memory:
                cache = self._classic_local_resource_cache(memory)
            if any(expected is not None and actual != int(expected) for actual, expected in (
                (cache.gold, current_gold), (cache.lumber, current_lumber),
                (cache.food_used, current_food), (cache.food_cap, current_food_cap),
            )):
                raise RuntimeError("当前输入的资源值与 3.0 本地玩家资源状态不一致")
            return cache
        try:
            native = self._native_resource_cache(None)
        except (TimeoutError, OSError) as exc:
            self._native_selection_unavailable = True
            self._native_fallback_reason = f"local-resource native timeout/failure: {exc}"
            with self._process_memory() as memory:
                native = self._classic_local_resource_cache(memory)
        if (
            current_gold is None and current_lumber is None
            and current_food is None and current_food_cap is None
        ):
            return native
        if (
            (current_gold is not None and native.gold != int(current_gold))
            or (current_lumber is not None and native.lumber != int(current_lumber))
            or (current_food is not None and native.food_used != int(current_food))
            or (current_food_cap is not None and native.food_cap != int(current_food_cap))
        ):
            raise RuntimeError("当前输入的资源值与本地玩家 native 状态不一致")
        return native


    def read_resources(
        self,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> tuple[int, int]:
        cache = self.read_resource_cache(current_gold, current_lumber, current_food, current_food_cap)
        return cache.gold, cache.lumber


    def set_gold(self, target: int, current_gold: int | None = None, current_lumber: int | None = None) -> int:
        cache = self.read_resource_cache(current_gold, current_lumber)
        delta = int(target) - cache.gold
        if delta:
            self.write_resource_cache(cache, target_gold=int(target))
        return delta


    def set_lumber(self, target: int, current_gold: int | None = None, current_lumber: int | None = None) -> int:
        cache = self.read_resource_cache(current_gold, current_lumber)
        delta = int(target) - cache.lumber
        if delta:
            self.write_resource_cache(cache, target_lumber=int(target))
        return delta


    def add_gold(self, amount: int) -> None:
        if not amount:
            return
        cache = self.validate_local_player_resource_cache(
            self.locate_local_player_resource_cache()
        )
        self.write_resource_cache(cache, target_gold=cache.gold + int(amount))


    def add_lumber(self, amount: int) -> None:
        if not amount:
            return
        cache = self.validate_local_player_resource_cache(
            self.locate_local_player_resource_cache()
        )
        self.write_resource_cache(cache, target_lumber=cache.lumber + int(amount))


    def add_gold_and_lumber(self, amount: int) -> None:
        if not amount:
            return
        cache = self.validate_local_player_resource_cache(
            self.locate_local_player_resource_cache()
        )
        self.write_resource_cache(
            cache,
            target_gold=cache.gold + int(amount),
            target_lumber=cache.lumber + int(amount),
        )


    def set_food(
        self,
        target_used: int | None = None,
        target_cap: int | None = None,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> ResourceCache:
        cache = self.read_resource_cache(current_gold, current_lumber, current_food, current_food_cap)
        if cache.source == "persistent native player state":
            return self.write_resource_cache(
                cache,
                target_food_used=target_used,
                target_food_cap=target_cap,
            )
        raise RuntimeError("历史资源地址写入已禁用，请重新读取本地玩家 native 状态")
