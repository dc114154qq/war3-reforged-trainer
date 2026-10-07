"""Semantic projection of profile layouts into the typed bridge configuration.

Only names live here. All game offsets come from the selected data profile;
the same projection generates C fields and Python wire values.
"""

BRIDGE_LAYOUT_PROJECTION = {
    "component_head": ("layouts", "component_list", "head"),
    "component_sentinel": ("layouts", "component_list", "sentinel"),
    "component_node": ("layouts", "component_list", "node"),
    "component_tag": ("layouts", "component_list", "tag"),
    "component_handle": ("layouts", "component_list", "handle"),
    "component_previous": ("layouts", "component_list", "previous"),
    "component_next": ("layouts", "component_list", "next"),
    "component_owner": ("layouts", "component_list", "owner"),
    "component_data": ("layouts", "component_list", "data"),
    "ability_owner": ("layouts", "ability", "unit_owner"),
    "ability_rawcode": ("layouts", "ability", "rawcode"),
    "ability_mirror_rawcode": ("layouts", "ability", "mirror_rawcode"),
    "ability_cache": ("layouts", "ability", "data_cache"),
    "ability_flags": ("layouts", "ability", "flags"),
    "ability_handle": ("layouts", "ability", "full_handle"),
    "ability_live_mask": ("layouts", "ability", "live_mask"),
    "ability_live_value": ("layouts", "ability", "live_value"),
    "ability_excluded_flags": ("layouts", "ability", "excluded_flags"),
    "effect_target_callback": ("layouts", "effect", "target_callback"),
    "talent_initialize_callback": ("layouts", "talent", "initialize_callback"),
    "talent_records": ("layouts", "talent", "snapshot_start"),
    "talent_record_stride": ("layouts", "talent", "record_stride"),
    "equipment_count": ("equipment_runtime", "equipment_count"),
    "equipment_records": ("equipment_runtime", "equipment_records"),
    "equipment_capacity": ("equipment_runtime", "equipment_capacity"),
    "equipment_record_stride": ("layouts", "equipment_record", "stride"),
    "equipment_record_state": ("layouts", "equipment_record", "state"),
    "item_flags": ("equipment_runtime", "item_flags"),
    "item_class": ("equipment_runtime", "item_class"),
    "item_equipment_type": ("equipment_runtime", "item_equipment_type"),
    "item_rawcode_mirror": ("equipment_runtime", "item_rawcode_mirror"),
    "item_equipment_mask": ("layouts", "item", "equipment_mask"),
}


def bridge_layout(data):
    values = dict(data["bridge_layout"])
    for name, path in BRIDGE_LAYOUT_PROJECTION.items():
        value = data
        for key in path:
            value = value[key]
        values[name] = value
    return values
