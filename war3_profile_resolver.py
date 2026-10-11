"""Unknown-build profile resolution. Exact builds return before any discovery I/O."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from war3_game_profile import (BorrowedGameProfile, BRIDGE_PROFILE_VERSION, SCHEMA_VERSION,
                               PROFILE_ROOT, ProfileError, _freeze)


@dataclass(frozen=True)
class ResolvedProfile(BorrowedGameProfile):
    evidence: object
    resolution_mode: str = "discovered"

    def selection_report(self):
        result = super().selection_report()
        result.update(mode=self.resolution_mode, automatic_discovery=True,
                      dependencies={name: value.to_dict() for name, value in self.evidence.items()})
        from war3_discovery_dependencies import DEPENDENCIES, missing_dependencies
        result['capability_dependencies'] = {name: list(missing_dependencies(self.evidence, required))
                                             for name, required in DEPENDENCIES.items()}
        return result

    def require_dependencies(self, name, request=None):
        from war3_discovery_dependencies import dependencies_for, missing_dependencies
        from war3_profile_discovery import DiscoveryError
        missing = missing_dependencies(self.evidence, dependencies_for(name, request))
        if missing:
            error=DiscoveryError("当前游戏版本的这项功能仍有数据未能确认；其他已确认功能可继续使用。",
                                 code="dependencies", evidence=tuple(self.evidence.values()))
            error.discovery_report.update(operation=name,missing=list(missing),
                actual_version=self.data['game_version'],source_version=self.source.data['game_version'])
            raise error

    def require_module(self, name):
        from war3_discovery_dependencies import missing_dependencies
        from war3_profile_discovery import DiscoveryError
        if missing_dependencies(self.evidence, ("modules."+name,)):
            raise DiscoveryError("当前游戏版本的这项扩展尚未完成自动定位。", code="dependencies",
                                 evidence=tuple(self.evidence.values()))
        # Recognized, bundled strategy only. Instruction-patching modules keep their gate.
        return super().require_module(name)


def _set(data, path, value):
    keys = path.split(".")
    parent = data
    for key in keys[:-1]: parent = parent[key]
    parent[keys[-1]] = value


def _merge_observations(updates, evidence, observed_updates, observed_evidence):
    """Unreadable observers cannot erase proof; contradictory observers invalidate it."""
    from war3_profile_discovery import DiscoveryEvidence
    for path, proof in observed_evidence.items():
        previous = evidence.get(path)
        if previous is not None and previous.state == 'confirmed':
            if proof.state == 'unresolved':
                continue
            if proof.state=='candidate' and proof.candidates==previous.candidates:
                # A less complete observer of the same member must not erase
                # the composite code + live-identity proof obtained earlier.
                continue
            if (proof.state == 'ambiguous' or
                    (proof.state=='candidate' and previous.candidates and proof.candidates and
                     proof.candidates!=previous.candidates) or
                    (proof.state=='confirmed' and previous.candidates and proof.candidates and
                     proof.candidates!=previous.candidates) or
                    (proof.state == 'confirmed' and path in updates and path in observed_updates
                     and updates[path] != observed_updates[path])):
                candidates = tuple(dict.fromkeys(previous.candidates + proof.candidates))
                evidence[path] = DiscoveryEvidence(path, 'ambiguous', 'conflicting_independent_observations',
                                                  candidates, previous.anchors + proof.anchors)
                updates.pop(path, None)
                continue
        if previous is not None and previous.state == 'ambiguous':
            # A later single observer cannot clear an existing disagreement.
            continue
        evidence[path] = proof
        if proof.state == 'confirmed' and path in observed_updates:
            updates[path] = observed_updates[path]
        elif proof.state != 'confirmed':
            updates.pop(path, None)


def _build(source, borrowed, updates, evidence, checks, mode):
    data = borrowed.to_dict()
    data["status"] = "discovered"
    # Only semantic data paths emitted by the locators are accepted. Not code or ABI.
    for path, value in updates.items():
        original = source.data
        for part in path.split('.'):
            if isinstance(original, tuple):
                original = original[int(part)]
            else:
                original = original[part]
        if path=='stat_runtime.flat_flag':
            if type(value) is not int or not 0<value<0x1000:
                raise ProfileError('Discovered stat discriminator exceeds bounded object')
            _set(data,path,value)
        elif path.startswith(("addresses.", "stat_runtime.")):
            if type(value) is not int or not 0 < value < borrowed.fingerprint[2]:
                raise ProfileError("Discovered address exceeds image")
            _set(data, path, value)
        elif (path.startswith("context.") or path in ("players.count", "players.array", "players.max_count", "players.normal_index",
                "layouts.unit.position_x", "layouts.unit.position_y", "bridge_layout.unit_attack", "selection.manager")):
            if type(value) is not int or not 0 < value < 0x10000:
                raise ProfileError("Discovered layout exceeds bounded object")
            _set(data, path, value)
        elif path.startswith(('native_table.', 'registry.')):
            alignment=4 if path in ('registry.object_rawcode','registry.count') else 8
            if type(value) is not int or not 0 <= value < 0x400 or value % alignment:
                raise ProfileError('Discovered native table member exceeds bounded aligned layout')
            _set(data, path, value)
        elif path.startswith(('layouts.', 'equipment_runtime.')):
            from war3_discovery_fields import ALLOWED_FIELDS
            from war3_discovery_properties import PROPERTY_PATHS
            from war3_discovery_components import COMPONENT_PATHS
            from war3_discovery_ability_identity import ABILITY_IDENTITY_PATHS
            if path not in ALLOWED_FIELDS | PROPERTY_PATHS | COMPONENT_PATHS | ABILITY_IDENTITY_PATHS or type(value) is not int or not 0 <= value < 0x10000:
                raise ProfileError('Unreviewed or unbounded discovered semantic member')
            _set(data, path, value)
        elif path.startswith("decoder."):
            if type(value) is not int or not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
                raise ProfileError("Invalid discovered decoder constant")
            if path in ("decoder.rol", "decoder.ror") and not 0 < value < 64:
                raise ProfileError("Invalid discovered decoder rotation")
            _set(data, path, value)
        elif path == "modules.legacy_layout.implementation":
            if value not in ("legacy_layout_24323_v1", "legacy_layout_24332_v1"):
                raise ProfileError("Unknown discovered decoder strategy")
            _set(data, path, value)
        elif not path.startswith('checks.'):
            raise ProfileError("Unsupported discovery data path: " + path)
    for group, rows in checks.items():
        if len(rows) != len(data["checks"][group]): raise ProfileError("Discovered check shape differs")
        if all(row is not None for row in rows): data["checks"][group] = rows
    data["bridge_layout"]["registry_root_rva"] = data["addresses"]["registry_root"]
    for key in ('primary','alternate','stride','slot_owner','owner_handle','owner_data','object_handle','object_rawcode'):
        data['bridge_layout'][key] = data['registry'][key]
    data['bridge_layout']['table_count'] = data['registry']['count']
    if data['equipment_runtime']['ability_owner'] != data['layouts']['ability']['unit_owner']:
        if 'layouts.ability.unit_owner' in updates and 'equipment_runtime.ability_owner' not in updates:
            data['equipment_runtime']['ability_owner'] = data['layouts']['ability']['unit_owner']
        else:
            raise ProfileError('Discovered ability and equipment ownership members disagree')
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return ResolvedProfile(_freeze(data), hashlib.sha256(encoded).hexdigest(), source,
                           MappingProxyType(dict(evidence)), mode)


class ProfileResolver:
    def __init__(self, catalog, *, cache=None, references=None, capture=None, digest=None):
        self.catalog = catalog
        self._cache, self._references = cache, references
        self._capture, self._digest = capture, digest

    def resolve(self, fingerprint, name, path, memory, base, *, selected=None,
                cancel=None, progress=None, budget_seconds=30, hwnd=0, pid=0):
        # No discovery imports, filesystem calls, hashing or extra game reads on exact hits.
        if selected is None:
            selected = self.catalog.select_for_image(fingerprint, name, path)
        if not isinstance(selected, BorrowedGameProfile): return selected
        from war3_profile_discovery import (DiscoveryCache, DiscoveryError, DiscoveryEvidence,
            DiscoveryImage, RECIPE_VERSION, ScanBudget, executable_digest)
        from war3_discovery_locators import locate
        from war3_discovery_dependencies import COMMON, missing_dependencies
        budget = ScanBudget(budget_seconds, cancel, progress)
        budget.check("正在为新版本自动定位")
        source = selected.source
        if self._references is None:
            book = json.loads((PROFILE_ROOT / "discovery" / "references.json").read_text(encoding="utf8"))
        else: book = self._references
        refs = book.get("sources", {}).get(source.data["game_version"], {})
        if (book.get("recipe_version") != RECIPE_VERSION or refs.get("source_digest") != source.digest):
            raise DiscoveryError("当前适配来源缺少匹配的定位规则，未沿用旧地址执行。", code="recipe")
        identity = dict(fingerprint=list(fingerprint), source=source.digest,
                        recipe=hashlib.sha256(json.dumps(book, sort_keys=True).encode()).hexdigest(),
                        schema=SCHEMA_VERSION, bridge=BRIDGE_PROFILE_VERSION,
                        executable=(self._digest or executable_digest)(path, fingerprint, budget))
        cache = self._cache or DiscoveryCache()
        cached = cache.load(identity)
        if cached is not None:
            try:
                candidate = self._restore_cached(source, selected, cached, memory, base, budget)
            except DiscoveryError:raise
            except (OSError, ValueError, KeyError, TypeError):
                candidate = None
            if candidate is not None:
                stat_recipes=refs['references'].get('stat_field_consumers',())
                if hwnd and pid and self._native_refresh_needed(candidate.evidence,stat_recipes=stat_recipes):
                    candidate = self._refresh_cached_natives(candidate, cached, identity, cache,
                                                              memory, base, hwnd, pid, budget,
                                                              semantic_recipes=refs['references'].get('semantic_fields',()),
                                                              real_forwarders=refs['references'].get('native_abi_forwarders',()),
                                                              stat_recipes=stat_recipes)
                budget.check("已使用本版本的定位缓存", 1)
                return candidate
        if self._capture is None:
            from war3_discovery_image import capture_image, file_type_descriptors
            from war3_discovery_locators import STAT_TYPES
            image = capture_image(memory, base, fingerprint, budget)
            image.type_descriptors = file_type_descriptors(path, fingerprint, tuple(STAT_TYPES.values())+('CAbility',), budget)
        else:
            image = self._capture(memory, base, fingerprint, budget)
        updates, evidence, checks = locate(image, source, refs["references"], budget)
        if hwnd and pid and "addresses.tls_index" in updates:
            from war3_discovery_native import discover_registrations, discover_active_registrations, read_window_tls, associate_tls
            try:
                tls = read_window_tls(memory, base, updates["addresses.tls_index"], hwnd, pid, budget)
                contexts, layout_updates, layout_evidence = discover_active_registrations(memory, image, source, tls, budget)
                _merge_observations(updates, evidence, layout_updates, layout_evidence)
                proof = layout_evidence.get('native_table', DiscoveryEvidence(
                    'native_table', 'unresolved', 'active_tls_registration_candidates'))
                if not contexts and proof.state != 'ambiguous':
                    contexts, proof = discover_registrations(memory, image, source, budget)
                    tls = read_window_tls(memory, base, updates["addresses.tls_index"], hwnd, pid, budget)
                association, slot_proof = associate_tls(memory, tls, contexts, budget)
                if association is not None and read_window_tls(memory, base, updates["addresses.tls_index"], hwnd, pid, budget) != tls:
                    association = None
                    slot_proof = DiscoveryEvidence('context.native_slot', 'unresolved', 'frame_changed')
                evidence["context.native_slot"] = slot_proof
                if association is not None:
                    evidence["native_table"] = DiscoveryEvidence("native_table", "confirmed", "active_tls_registration_chain")
                    updates["context.native_slot"] = association[0]
                    from war3_discovery_locators import native_call_and_field_evidence
                    native_updates, native_evidence = native_call_and_field_evidence(
                        image, contexts[association[1]], budget)
                    from war3_discovery_locators import native_attack_layout
                    attack_updates, attack_evidence = native_attack_layout(image, contexts[association[1]], budget)
                    native_updates.update(attack_updates)
                    native_evidence.update(attack_evidence)
                    _merge_observations(updates, evidence, native_updates, native_evidence)
                    semantic_recipes=refs['references'].get('semantic_fields',())
                    if any('binding' in row for row in semantic_recipes):
                        from war3_discovery_fields import locate_semantic_fields
                        field_updates,field_evidence=locate_semantic_fields(image,semantic_recipes,budget,
                            entries=contexts[association[1]],resolver=evidence.get('addresses.unit_resolver'))
                        _merge_observations(updates,evidence,field_updates,field_evidence)
                    from war3_discovery_fields import native_scalar_members
                    scalar_updates,scalar_evidence=native_scalar_members(image,contexts[association[1]],evidence,budget)
                    _merge_observations(updates,evidence,scalar_updates,scalar_evidence)
                    from war3_discovery_selection import native_selection_manager
                    evidence['selection.native_manager'] = native_selection_manager(
                        image, contexts[association[1]], budget)
                    from war3_discovery_locators import native_abi_evidence
                    abi = native_abi_evidence(image, contexts[association[1]], budget,
                        real_forwarders=refs['references'].get('native_abi_forwarders',()))
                    if evidence['addresses.unit_resolver'].state == 'confirmed':
                        evidence['native_abi'] = abi
                    else:
                        evidence['native_abi'] = DiscoveryEvidence('native_abi', 'unresolved',
                            'handle_abi_unconfirmed', anchors=abi.anchors,
                            detail='Primitive ABI observation: '+abi.state+'/'+abi.method+'; '+abi.detail)
                else:
                    evidence["native_table"] = proof
            except OSError as exc:
                evidence["native_table"] = DiscoveryEvidence("native_table", "unresolved", "read_error", detail=str(exc))
        # A version-resource-only update can retain the complete executable code.
        # This is a whole-section witness, not a few matching AOBs or nearest-version guess.
        text_identity = refs.get("text_identity", {})
        try:
            unchanged = (hashlib.sha256(image.read(text_identity["rva"], text_identity["size"])).hexdigest()
                         == text_identity["sha256"])
            data_witnesses = refs.get("static_identity", ())
            unchanged = unchanged and {row['section'] for row in data_witnesses} == {'.rdata', '.pdata'}
            if unchanged:
                unchanged = all(image.canonical_digest(row['rva'], row['size'],
                                pointers=row['section']=='.rdata', budget=budget)==row['sha256']
                                for row in data_witnesses)
        except (OSError, KeyError):
            unchanged = False
        if unchanged:
            from war3_discovery_dependencies import DEPENDENCIES
            updates.update({"addresses."+key: value for key, value in source.section("addresses").items()})
            checks = source.to_dict()["checks"]
            for dependency in set().union(*DEPENDENCIES.values()):
                # RTTI-backed tables must be independently found; cancelled patches stay absent.
                if dependency in ("stat_runtime", "module_addresses", "modules.talent_icons"):
                    continue
                evidence[dependency] = DiscoveryEvidence(dependency, "confirmed", "complete_code_and_static_identity")
            if all(evidence.get("stat_runtime."+key) is not None and
                   evidence["stat_runtime."+key].state == "confirmed"
                   for key in ("cooldown_vtable", "amplification_vtable", "spell_vamp_vtable", "resolve_vtable")):
                evidence["stat_runtime"] = DiscoveryEvidence("stat_runtime", "confirmed", "complete_text_and_rtti")
        candidate = _build(source, selected, updates, evidence, checks, "discovered")
        # A candidate cannot become a usable adapter merely because several RVAs matched.
        # Validators are read-only and each group has its own evidence requirements.
        from war3_discovery_validation import validate_common
        candidate, evidence = validate_common(candidate, image, memory, base, budget)
        for path,proof in evidence.items():
            if (proof.state=='confirmed' and len(proof.candidates)==1 and proof.method in (
                'tagged_states_packed_ids_and_owner_backlinks','proved_record_member_span',
                'canonical_component_links_and_registry_owners','native_cooldown_and_canonical_attack_components')):
                updates[path]=proof.candidates[0]
            elif (proof.state=='confirmed' and len(proof.candidates)==1 and
                  proof.method=='canonical_ability_handles_and_base_class_rtti'):
                updates[path]=proof.candidates[0]
        candidate=_build(source,selected,updates,evidence,checks,'discovered')
        selection_proof = evidence.get('selection.manager')
        if selection_proof is not None and selection_proof.state == 'confirmed':
            updates['selection.manager'] = selection_proof.candidates[0]
            candidate = _build(source, selected, updates, evidence, checks, 'discovered')
        missing = missing_dependencies(evidence, COMMON)
        if missing:
            proof = tuple(evidence.values())
            error = DiscoveryError("已识别游戏版本，但公共读取依赖尚未全部定位；未开始游戏修改。",
                                   code="common_dependencies", evidence=proof)
            error.discovery_report.update(missing=list(missing), unreadable_pages=len(image.unreadable),
                                          updates=updates, actual_version=selected.data["game_version"],
                                          source_version=source.data["game_version"])
            raise error
        payload = dict(updates=updates, checks=checks,
                       evidence={key: value.to_dict() for key, value in evidence.items()})
        try: cache.save(identity, payload)
        except OSError: pass  # Storage failure must not disable a resolved session.
        budget.check("已完成公共定位，功能按已确认范围启用", 1)
        return candidate

    @staticmethod
    def _native_refresh_needed(evidence,*,stat_recipes=()):
        # An ABI proof does not imply that every protected native body was
        # readable. Reconnect can fill those leaves without a global AOB scan.
        from war3_discovery_dependencies import missing_dependencies
        required=(
            'native_abi', 'addresses.unit_resolver', 'selection.native_manager',
            'bridge_layout.unit_attack', 'layouts.unit.position_x', 'layouts.unit.position_y',
            'layouts.property.maximum')
        if stat_recipes:required+=('stat_runtime.flat_flag',)
        return bool(missing_dependencies(evidence,required))

    @staticmethod
    def _refresh_cached_natives(candidate, cached, identity, cache, memory, base, hwnd, pid, budget, *, semantic_recipes=(),real_forwarders=(),stat_recipes=()):
        """A protected page may become readable on a later connection.

        Revisit only unresolved native evidence; never perform another global
        function scan or replay the user's operation on a cache hit.
        """
        from war3_discovery_image import capture_image
        from war3_discovery_native import read_window_tls, discover_active_registrations, associate_tls
        from war3_discovery_locators import native_call_and_field_evidence, native_abi_evidence
        from war3_profile_discovery import DiscoveryError, DiscoveryEvidence
        try:
            image = capture_image(memory, base, candidate.fingerprint, budget)
            tls = read_window_tls(memory, base, candidate.section('addresses')['tls_index'], hwnd, pid, budget)
            contexts, layout_updates, layout_evidence = discover_active_registrations(memory, image, candidate, tls, budget)
            association, _ = associate_tls(memory, tls, contexts, budget)
            if association is None:
                return candidate
            updates, observed = native_call_and_field_evidence(image, contexts[association[1]], budget)
            from war3_discovery_locators import native_attack_layout
            from war3_discovery_selection import native_selection_manager
            from war3_discovery_validation import refresh_selection_evidence
            attack_updates, attack_evidence = native_attack_layout(image, contexts[association[1]], budget)
            updates.update(attack_updates)
            observed.update(attack_evidence)
            selection_native = native_selection_manager(image, contexts[association[1]], budget)
            proof = dict(candidate.evidence)
            changes = dict(cached['updates'])
            _merge_observations(changes, proof, layout_updates, layout_evidence)
            _merge_observations(changes, proof, updates, observed)
            if stat_recipes:
                from war3_discovery_stats import locate_stat_mode,reconcile_stat_mode
                stat_updates,stat_proofs=locate_stat_mode(image,stat_recipes,proof,budget)
                _merge_observations(changes,proof,stat_updates,stat_proofs)
                reconcile_stat_mode(proof)
            if semantic_recipes:
                from war3_discovery_fields import locate_semantic_fields
                hints={a[0] for p in candidate.evidence.values() if p.method in
                       ('independent_semantic_consumers','semantic_corroborator_missing')
                       for a in p.anchors if isinstance(a,(tuple,list)) and len(a)==2 and type(a[0]) is int}
                field_updates,field_proofs=locate_semantic_fields(image,semantic_recipes,budget,
                    entries=contexts[association[1]],site_hints=tuple(hints),resolver=proof.get('addresses.unit_resolver'))
                _merge_observations(changes,proof,field_updates,field_proofs)
            from war3_discovery_fields import native_scalar_members
            scalar_updates,scalar_evidence=native_scalar_members(image,contexts[association[1]],proof,budget)
            _merge_observations(changes,proof,scalar_updates,scalar_evidence)
            confirmed = refresh_selection_evidence(proof,selection_native)
            if confirmed is not None:
                changes['selection.manager'] = confirmed.candidates[0]
            if read_window_tls(memory, base, candidate.section('addresses')['tls_index'], hwnd, pid, budget) != tls:
                return candidate
            if proof['addresses.unit_resolver'].state == 'confirmed':
                abi = native_abi_evidence(image, contexts[association[1]], budget,real_forwarders=real_forwarders)
                if abi.state == 'confirmed':
                    proof['native_abi'] = abi
            result = _build(candidate.source, candidate, changes, proof, cached['checks'], 'discovery_cache')
            payload = dict(updates=changes, checks=cached['checks'],
                           evidence={key: value.to_dict() for key, value in proof.items()})
            try: cache.save(identity, payload)
            except OSError: pass
            return result
        except DiscoveryError as exc:
            if exc.discovery_report['code'] in ('cancelled', 'timeout', 'budget', 'identity'):
                raise
            return candidate
        except (OSError, ValueError):
            return candidate

    def _restore_cached(self, source, borrowed, cached, memory, base, budget):
        from war3_profile_discovery import DiscoveryEvidence,DiscoveryError
        from war3_discovery_dependencies import COMMON, missing_dependencies
        evidence = {key: DiscoveryEvidence(**value) for key, value in cached["evidence"].items()}
        if missing_dependencies(evidence, COMMON): return None
        for path, value in cached['updates'].items():
            if path.startswith('checks.'):
                continue
            proof = evidence.get(path)
            if proof is None or proof.state != 'confirmed':
                return None
            if proof.candidates != (value,):
                # Whole-image proofs can reuse only the exact source value.
                if proof.method != 'complete_code_and_static_identity':
                    return None
                original = source.data
                for part in path.split('.'):
                    original = original[part]
                if original != value:
                    return None
        checks = cached["checks"]
        readable_image = None
        # Validate the complete stored anchor set against this process. A single mismatch
        # or unreadable page returns to discovery; no stale candidate is dispatched.
        for rows in checks.values():
            for row in rows:
                expected = bytes.fromhex(row["bytes"])
                rva = row["rva"]
                if not expected or not 0 < rva < rva+len(expected) <= borrowed.fingerprint[2]: return None
                try:
                    observed = budget.read(memory, base+rva, len(expected))
                except OSError:
                    if readable_image is None:
                        if self._capture is not None:
                            readable_image = self._capture(memory, base, borrowed.fingerprint, budget)
                        else:
                            from war3_discovery_image import capture_image
                            readable_image = capture_image(memory, base, borrowed.fingerprint, budget)
                    observed = readable_image.read(rva, len(expected))
                if observed != expected: return None
        # Advanced fields have their own consumers. Common resolver/TLS bytes
        # alone cannot attest a cached member inferred in another function.
        semantic_anchors=set()
        for proof in evidence.values():
            if proof.state != 'confirmed' or proof.method not in ('independent_semantic_consumers','typed_native_scalar_member_return',
                'cross_checked_typed_native_machine_conventions','typed_native_machine_conventions',
                'typed_native_unit_resolver_callers',
                'typed_coordinate_getter_and_setter',
                'typed_unit_selected_player_manager',
                'native_cooldown_and_canonical_attack_components'):continue
            needed=(3 if proof.method=='typed_native_machine_conventions' else
                    1 if proof.method in ('typed_native_scalar_member_return','typed_unit_selected_player_manager',
                    'native_cooldown_and_canonical_attack_components') else 2)
            if len(proof.anchors)<needed:return None
            sites=set()
            for anchor in proof.anchors:
                if not isinstance(anchor,(list,tuple)) or len(anchor)!=2:return None
                rva,hex_code=anchor
                if type(rva) is not int or not isinstance(hex_code,str):return None
                expected=bytes.fromhex(hex_code)
                minimum=12 if proof.method in ('cross_checked_typed_native_machine_conventions','typed_native_machine_conventions',
                    'typed_native_unit_resolver_callers','typed_coordinate_getter_and_setter') else 24
                if not minimum<=len(expected)<=1024 or not 0<rva<rva+len(expected)<=borrowed.fingerprint[2]:return None
                sites.add(rva)
                semantic_anchors.add((rva,expected))
            if len(sites)<needed:return None
        for rva,expected in semantic_anchors:
            try:observed=budget.read(memory,base+rva,len(expected))
            except OSError:
                if readable_image is None:
                    if self._capture is not None:
                        readable_image=self._capture(memory,base,borrowed.fingerprint,budget)
                    else:
                        from war3_discovery_image import capture_image
                        readable_image=capture_image(memory,base,borrowed.fingerprint,budget)
                observed=readable_image.read(rva,len(expected))
            if observed != expected:return None
        # Mode flags are bound to individual RTTI class tables. Recheck both
        # complete code bodies and their current virtual-method targets.
        import struct
        for proof in evidence.values():
            if proof.state!='confirmed' or proof.method not in ('class_bound_stat_mode_consumers','all_class_bound_stat_mode_consumers'):continue
            bodies=[];links=[]
            for anchor in proof.anchors:
                if not isinstance(anchor,tuple):return None
                if len(anchor)==2:
                    rva,hex_code=anchor
                    if type(rva) is not int or not isinstance(hex_code,str):return None
                    expected=bytes.fromhex(hex_code)
                    if not 24<=len(expected)<=1024 or not 0<rva<rva+len(expected)<=borrowed.fingerprint[2]:return None
                    bodies.append((rva,expected))
                elif len(anchor)==4 and anchor[0]=='method':
                    _,table,slot,rva=anchor
                    if (any(type(value) is not int for value in (table,slot,rva)) or slot not in (15,36) or
                        not 0<table<table+(slot+1)*8<=borrowed.fingerprint[2] or
                        not 0<rva<borrowed.fingerprint[2]):return None
                    links.append((table,slot,rva))
                else:return None
            needed=8 if proof.method=='all_class_bound_stat_mode_consumers' else 2
            if (len(bodies)!=needed or len(links)!=needed or len({at for at,_ in bodies})<2 or
                    {at for at,_ in bodies}!={at for _,_,at in links}):return None
            def mode_read(rva,size):
                nonlocal readable_image
                try:return budget.read(memory,base+rva,size)
                except OSError:
                    if readable_image is None:
                        if self._capture is not None:readable_image=self._capture(memory,base,borrowed.fingerprint,budget)
                        else:
                            from war3_discovery_image import capture_image
                            readable_image=capture_image(memory,base,borrowed.fingerprint,budget)
                    return readable_image.read(rva,size)
            for at,expected in bodies:
                if mode_read(at,len(expected))!=expected:return None
            for table,slot,at in links:
                if struct.unpack('<Q',mode_read(table+slot*8,8))[0]!=base+at:return None
        # A cached RTTI-derived table is independent of resolver/TLS code.
        # Check its current COL and method targets using process-relative
        # values, so a new module base never preserves stale absolute pointers.
        import struct
        for proof in evidence.values():
            if proof.state!='confirmed' or not proof.method.startswith('msvc_rtti:'):continue
            if len(proof.candidates)!=1 or len(proof.anchors)!=1:return None
            anchor=proof.anchors[0]
            if not isinstance(anchor,tuple) or len(anchor)!=4:return None
            table,col,hex_header,methods=anchor
            if (type(table) is not int or type(col) is not int or proof.candidates!=(table,) or
                not isinstance(hex_header,str) or not isinstance(methods,tuple) or len(methods)!=3 or
                not 8<=table<table+24<=borrowed.fingerprint[2] or
                not 0<col<col+24<=borrowed.fingerprint[2] or
                any(type(value) is not int or not 0<value<borrowed.fingerprint[2] for value in methods)):
                return None
            expected=bytes.fromhex(hex_header)
            if len(expected)!=24:return None
            header=struct.unpack('<6I',expected)
            if (header[0],header[1],header[2],header[5])!=(1,0,0,col):return None
            def rtti_read(rva,size):
                nonlocal readable_image
                try:return budget.read(memory,base+rva,size)
                except OSError:
                    if readable_image is None:
                        if self._capture is not None:readable_image=self._capture(memory,base,borrowed.fingerprint,budget)
                        else:
                            from war3_discovery_image import capture_image
                            readable_image=capture_image(memory,base,borrowed.fingerprint,budget)
                    return readable_image.read(rva,size)
            if struct.unpack('<Q',rtti_read(table-8,8))[0]!=base+col:return None
            if rtti_read(col,24)!=expected:return None
            observed_methods=tuple(value-base for value in struct.unpack('<3Q',rtti_read(table,24)))
            if observed_methods!=methods:return None
        candidate=_build(source, borrowed, cached["updates"], evidence, checks, "discovery_cache")
        read_proof=evidence.get('selection.read_only')
        if read_proof is not None and read_proof.method=='current_map_canonical_list_read':
            # A build cache contains member offsets, never current map identity
            # evidence. Recheck only the stored member; do not scan on a hit.
            from war3_discovery_selection import locate_selection_graph
            from war3_discovery_validation import confirm_selection_read
            from war3_discovery_native import BudgetMemory
            from war3_object_registry import ObjectRegistry24268
            from war3_game_profile import profile_scope
            try:
                with profile_scope(candidate):
                    registry=ObjectRegistry24268(memory,base)
                    rings=locate_selection_graph(candidate,BudgetMemory(memory,budget),registry,budget,radius=0)
                current=confirm_selection_read(evidence.get('selection.native_manager'),rings)
                if current is None or current.candidates!=read_proof.candidates:return None
            except DiscoveryError:raise
            except (OSError,ValueError,RuntimeError):return None
        graph_fields={path:proof for path,proof in evidence.items() if
                      proof.state=='confirmed' and proof.method=='tagged_states_packed_ids_and_owner_backlinks'}
        if graph_fields:
            # A prior map's graph is not immutable build evidence. Reconnect
            # must find the same identities in this map before retaining it.
            from war3_object_registry import ObjectRegistry24268
            from war3_game_profile import profile_scope
            from war3_discovery_properties import discover_player_property_identity
            try:
                with profile_scope(candidate):
                    registry=ObjectRegistry24268(memory,base)
                    players=registry.players(memory)
                    live_updates,live_evidence=discover_player_property_identity(memory,registry,players,candidate,budget)
                if any(path not in live_updates or live_updates[path]!=cached['updates'].get(path)
                       for path in graph_fields):return None
            except DiscoveryError:raise
            except (OSError,ValueError,RuntimeError):
                return None
        component_fields={path:proof for path,proof in evidence.items() if path.startswith('layouts.component_list.') and
                          proof.state=='confirmed' and proof.method=='canonical_component_links_and_registry_owners'}
        if component_fields:
            from war3_discovery_components import discover_profile_components
            from war3_game_profile import profile_scope
            from war3_object_registry import ObjectRegistry24268
            try:
                with profile_scope(candidate):
                    registry=ObjectRegistry24268(memory,base)
                    live_updates,_=discover_profile_components(candidate,memory,registry,
                        candidate.evidence.get('selection.manager'),budget)
                if any(live_updates.get(path)!=cached['updates'].get(path) for path in component_fields):return None
                attack_proof=candidate.evidence.get('bridge_layout.unit_attack')
                if attack_proof is not None and attack_proof.method=='native_cooldown_and_canonical_attack_components':
                    from war3_discovery_components import component_probe_units,confirm_attack_member
                    members={path.rsplit('.',1)[1]:value for path,value in live_updates.items()}
                    units=component_probe_units(candidate,memory,registry,candidate.evidence.get('selection.manager'),budget)
                    proof=confirm_attack_member(memory,registry,units,members,attack_proof,budget)
                    if proof is None or proof.state!='confirmed':return None
                identity_fields={path:proof for path,proof in evidence.items() if proof.state=='confirmed' and
                                 proof.method=='canonical_ability_handles_and_base_class_rtti'}
                if identity_fields:
                    from war3_discovery_ability_identity import discover_ability_identity
                    descriptors=set.intersection(*(set(proof.anchors) for proof in identity_fields.values()))
                    if not descriptors or any(type(v) is not int or not 0<v<borrowed.fingerprint[2] for v in descriptors):return None
                    if readable_image is None:
                        if self._capture is not None:readable_image=self._capture(memory,base,borrowed.fingerprint,budget)
                        else:
                            from war3_discovery_image import capture_image
                            readable_image=capture_image(memory,base,borrowed.fingerprint,budget)
                    readable_image.type_descriptors={'CAbility':tuple(descriptors)}
                    members={path.rsplit('.',1)[1]:value for path,value in live_updates.items()}
                    from war3_discovery_components import component_probe_units
                    units=component_probe_units(candidate,memory,registry,candidate.evidence.get('selection.manager'),budget)
                    observed,_=discover_ability_identity(memory,registry,units,members,readable_image,budget)
                    if any(observed.get(path)!=cached['updates'].get(path) for path in identity_fields):return None
            except DiscoveryError:raise
            except (OSError,ValueError,RuntimeError):return None
        return candidate
