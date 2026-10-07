"""Strict data-only equipment plans with atomic writes and no live pointers."""
import json
import os
import tempfile
from pathlib import Path


def validate_records(records):
    if not isinstance(records, list) or len(records) > 512:
        raise ValueError('Invalid equipment plan list')
    result = []
    for record in records:
        if not isinstance(record, dict) or set(record) != {'name', 'unit_type_id', 'equipment', 'equipment_charges', 'requires_any_slot'}:
            raise ValueError('Invalid equipment plan fields')
        name = record['name']
        if not isinstance(name, str) or not name.strip() or len(name) > 64:
            raise ValueError('Invalid equipment plan name')
        if type(record['unit_type_id']) is not int or not 0 <= record['unit_type_id'] <= 0xffffffff:
            raise ValueError('Invalid hero type')
        rows, charges = record['equipment'], record['equipment_charges']
        if not isinstance(rows, (list, tuple)) or len(rows) != 9 or not isinstance(charges, (list, tuple)) or len(charges) != 9:
            raise ValueError('Equipment plans must have nine slots')
        layout = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                raise ValueError('Invalid equipment plan slot')
            rawcode, kind = row
            if type(rawcode) is not int or not 0 <= rawcode <= 0xffffffff or type(kind) is not int or not 0 <= kind <= 9:
                raise ValueError('Invalid equipment ID or type')
            if rawcode and any(not 32 <= byte <= 126 for byte in rawcode.to_bytes(4, 'big')):
                raise ValueError('Equipment ID is not a printable FourCC')
            layout.append((0, rawcode, kind))
        if any(type(value) is not int or not 0 <= value <= 1_000_000_000 for value in charges) or type(record['requires_any_slot']) is not bool:
            raise ValueError('Invalid equipment quantity or any-slot flag')
        result.append(dict(record, equipment=tuple(layout), equipment_charges=tuple(charges), target_unit=0))
    return result


def save_file(host, path):
    records = []
    for per_target in getattr(host, '_extension_saved_loadouts', {}).values():
        for record in per_target.values():
            records.append(dict(name=record['name'], unit_type_id=int(record.get('unit_type_id', 0)),
                equipment=[(int(row[1]), int(row[2]) if len(row) > 2 else 0) for row in record['equipment']],
                equipment_charges=list(record.get('equipment_charges', (0,) * 9)),
                requires_any_slot=bool(record.get('requires_any_slot', False))))
    validate_records(records)
    destination = Path(path)
    fd, pending = tempfile.mkstemp(prefix=destination.name + '.', suffix='.tmp', dir=destination.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(dict(schema=1, records=records), stream, ensure_ascii=False, indent=2)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(pending, destination)
    finally:
        if os.path.exists(pending): os.unlink(pending)
    return len(records)


def load_file(host, path):
    source = Path(path)
    if source.stat().st_size > 2_000_000:
        raise ValueError('Equipment plan file is too large')
    value = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or set(value) != {'schema', 'records'} or type(value['schema']) is not int or value['schema'] != 1:
        raise ValueError('Unsupported equipment plan schema')
    records = validate_records(value['records'])
    # Imported records contain no process or object identity. Bind only their
    # catalogue ownership to the current trainer; restore creates new items.
    host._extension_saved_loadouts = {(int(host.pid), -index-1): {r['name']: r} for index, r in enumerate(records)}
    host._extension_saved_loadout = None
    return len(records)
