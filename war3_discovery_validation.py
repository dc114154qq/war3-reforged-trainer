"""Evidence promotion rules. Never promote an inherited offset by numerical plausibility."""
from dataclasses import replace
from types import MappingProxyType
from war3_profile_discovery import DiscoveryEvidence, DiscoveryError


def confirm_selection(native, rings):
    """Both a native consumer and canonical live rings must name one member."""
    if (native is None or native.state != 'confirmed' or
            rings is None or rings.state not in ('candidate', 'confirmed') or
            native.candidates != rings.candidates):
        return None
    return DiscoveryEvidence('selection.manager', 'confirmed',
                             'native_selected_group_and_live_unit_rings',
                             rings.candidates, native.anchors)


def confirm_selection_read(native, rings):
    """Approve canonical list reads, without approving native manager semantics.

    The graph probe has checked every player's bounded ring and resolved all
    nonempty entries against this map's registry. A contrary native observation
    vetoes the read; protected native code is not a dependency of an external
    list traversal. The whole selection group still requires confirm_selection.
    """
    if (rings is None or len(rings.candidates) != 1 or not (
            rings.state == 'candidate' and rings.method == 'canonical_rings_all_players_and_unit_identity' or
            rings.state == 'confirmed' and rings.method in (
                'current_map_canonical_list_member', 'native_selected_group_and_live_unit_rings'))):
        return None
    if selection_conflict(native,rings):
        return None
    return DiscoveryEvidence('selection.read_only', 'confirmed',
                             'current_map_canonical_list_read', rings.candidates,
                             detail='Unique nonempty canonical player rings and current unit identities; '
                                    'external reads only, native manager semantics not implied')


def selection_conflict(native,rings):
    return native is not None and (native.state == 'ambiguous' or
        native.state == 'confirmed' and rings is not None and native.candidates != rings.candidates)


def refresh_selection_evidence(evidence,native):
    """Reconcile bounded native observations with an already revalidated map ring."""
    from war3_profile_resolver import _merge_observations
    # Conflicts stay unresolved across later protected/unreadable observations.
    _merge_observations({},evidence,{}, {'selection.native_manager':native})
    native=evidence['selection.native_manager']
    rings=evidence.get('selection.manager')
    if selection_conflict(native,rings):
        for key in ('selection.read_only','selection'):
            evidence[key]=DiscoveryEvidence(key,'unresolved','selection_native_graph_conflict',
                detail='Native selection access disagrees with the current canonical list member')
        return None
    read=confirm_selection_read(native,rings)
    if read is not None:evidence['selection.read_only']=read
    confirmed=confirm_selection(native,rings)
    if confirmed is not None:
        evidence['selection.manager']=confirmed
        evidence['selection']=DiscoveryEvidence('selection','confirmed','native_selected_group_and_live_unit_rings')
    return confirmed


def confirm_owner_handle(candidate, memory, registry, players, budget):
    """A generation operand is only a hint until the complete backlink agrees."""
    import struct
    proof = candidate.evidence.get('registry.owner_handle')
    if proof is None or proof.state != 'candidate' or len(proof.candidates) != 1:
        return None
    member = proof.candidates[0]
    if member != candidate.section('registry')['owner_handle']:
        # A changed complete-handle member needs its own bootstrap probe;
        # the existing player graph has not used it and cannot attest it.
        return None
    for player in players:
        budget.check('正在核对完整对象句柄')
        full = struct.unpack('<Q', memory.read(player+candidate.section('registry')['object_handle'], 8))[0]
        owner = registry.resolve_handle(memory, full)
        if struct.unpack('<Q', memory.read(owner+member, 8))[0] != full:
            return None
    return DiscoveryEvidence('registry.owner_handle', 'confirmed',
                             'resolver_generation_and_complete_live_backlinks', (member,), proof.anchors)


def validate_common(candidate, image, memory, base, budget):
    evidence = dict(candidate.evidence)
    if all(evidence.get('context.'+key) is not None and
           evidence['context.'+key].state=='confirmed' for key in candidate.section('context')):
        evidence['context']=DiscoveryEvidence('context','confirmed','all_context_fields_observed')
    # Group evidence must describe every field consumed by that group. Discovery of
    # an object resolver alone does not establish player/selection or native ABI layouts.
    complete_checks = all(
        evidence.get(f"checks.{group}.{index}") is not None and
        evidence[f"checks.{group}.{index}"].state == "confirmed"
        for group, rows in candidate.data["checks"].items() for index, _ in enumerate(rows))
    if complete_checks:
        evidence["checks"] = DiscoveryEvidence("checks", "confirmed", "all_code_anchors_unique")
    # Readback validates actual root ownership, not an arbitrary nonzero pointer.
    if complete_checks and evidence.get("addresses.registry_root", None) is not None:
        from war3_game_profile import profile_scope, GameProfile, _freeze
        from war3_object_registry import ObjectRegistry24268
        try:
            budget.check("正在核对公共对象结构")
            # A bounded read-only graph probe may inspect a candidate strategy
            # before the public operation gate approves it. Never return this
            # probe profile or expose it to an execution/write backend.
            probe_data = candidate.to_dict()
            for module in probe_data['modules'].values():
                module['fingerprint'] = list(candidate.fingerprint)
            probe = GameProfile(_freeze(probe_data), candidate.digest)
            with profile_scope(probe):
                registry = ObjectRegistry24268(memory, base)
                players = registry.players(memory)
            if players:
                # This verifies the current object graph, but does not establish local
                # player index, TLS layout, arbitrary field layouts or C calling ABI.
                evidence["registry_live"] = DiscoveryEvidence("registry_live", "confirmed", "registry_player_graph")
                from war3_discovery_properties import discover_player_property_identity,resource_snapshot_bounds
                property_updates,property_evidence=discover_player_property_identity(
                    memory,registry,players,candidate,budget)
                evidence.update(property_evidence)
                _,span_evidence=resource_snapshot_bounds(evidence)
                evidence.update(span_evidence)
                handle_proof = confirm_owner_handle(candidate, memory, registry, players, budget)
                if handle_proof is not None:
                    evidence['registry.owner_handle'] = handle_proof
                from war3_discovery_selection import locate_selection_graph
                from war3_discovery_native import BudgetMemory
                selection=locate_selection_graph(candidate,BudgetMemory(memory,budget),registry,budget)
                evidence['selection.manager']=selection
                native = evidence.get('selection.native_manager')
                read_proof = confirm_selection_read(native, selection)
                if read_proof is not None:
                    evidence['selection.read_only'] = read_proof
                    evidence['selection.manager'] = replace(selection, state='confirmed',
                        method='current_map_canonical_list_member',
                        detail='Canonical list member for external reads; native corroboration is separate')
                confirmed = confirm_selection(native, selection)
                if confirmed is not None:
                    evidence['selection.manager'] = confirmed
                    evidence['selection'] = DiscoveryEvidence(
                        'selection', 'confirmed', 'native_selected_group_and_live_unit_rings')
                from war3_discovery_components import discover_profile_components
                try:
                    _,component_proofs=discover_profile_components(candidate,memory,registry,selection,budget)
                    evidence.update(component_proofs)
                    if component_proofs.get('layouts.component_list') is not None and component_proofs['layouts.component_list'].state=='confirmed':
                        from war3_discovery_components import component_probe_units,confirm_attack_member
                        members={path.rsplit('.',1)[1]:proof.candidates[0] for path,proof in component_proofs.items() if proof.candidates}
                        units=component_probe_units(candidate,memory,registry,selection,budget)
                        attack=confirm_attack_member(memory,registry,units,members,evidence.get('bridge_layout.unit_attack'),budget)
                        if attack is not None:evidence['bridge_layout.unit_attack']=attack
                        from war3_discovery_ability_identity import discover_ability_identity
                        _,identity_proofs=discover_ability_identity(memory,registry,units,members,image,budget)
                        evidence.update(identity_proofs)
                except DiscoveryError:raise
                except (OSError,ValueError,RuntimeError) as exc:
                    evidence['layouts.component_list']=DiscoveryEvidence('layouts.component_list','unresolved',
                        'canonical_component_links_and_registry_owners',detail=str(exc))
                resolver = evidence.get('addresses.object_resolver')
                if resolver is not None and resolver.state=='confirmed' and resolver.method=='instruction_shape':
                    evidence['registry']=DiscoveryEvidence('registry','confirmed','resolver_code_and_live_owner_graph')
                    if evidence.get('decoder') is not None and evidence['decoder'].state=='confirmed':
                        evidence['modules.legacy_layout']=DiscoveryEvidence('modules.legacy_layout','confirmed','bundled_decoder_and_registry_graph')
        except DiscoveryError:
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            evidence["registry_live"] = DiscoveryEvidence("registry_live", "unresolved", "registry_player_graph", detail=str(exc))
    return replace(candidate, evidence=MappingProxyType(evidence)), evidence
