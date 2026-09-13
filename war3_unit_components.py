"""24268 intrusive ability/component list, rooted in the live unit owner."""
import struct


def read_unit_component_nodes(memory, registry, owner):
    def pointer(value):
        return 0x10000 <= value < 0x800000000000 and value % 8 == 0

    unit = memory.read_u64(owner + 0x90)
    handle, resolved_owner = registry.resolve_unit(memory, unit)
    if resolved_owner != owner:
        raise RuntimeError("Component owner mismatches unit registry")

    def traverse():
        head = memory.read_u64(owner + 0xD8)
        previous, node = owner + 0xD0, head
        visited, identities, result = set(), [], []
        while node:
            if not pointer(node) or node in visited or len(visited) >= 4096:
                raise RuntimeError("Invalid or cyclic unit component list")
            visited.add(node)
            wrapper = node - 0x38
            raw = memory.read(wrapper + 0x18, 0x80)
            tag, full_handle = struct.unpack_from("<QQ", raw)
            prior, following = struct.unpack_from("<QQ", raw, 0x20)
            backlink = struct.unpack_from("<Q", raw, 0x38)[0]
            data = struct.unpack_from("<Q", raw, 0x78)[0]
            if prior != previous or backlink != owner:
                raise RuntimeError("Unit component link changed or has wrong owner")
            if registry.resolve_handle(memory, full_handle) != wrapper:
                raise RuntimeError("Component handle mismatches registry")
            identities.append((wrapper, tag, full_handle, prior, following, data))
            result.append((tag, wrapper, full_handle, data))
            previous, node = node, following
        if memory.read_u64(owner + 0xD8) != head:
            raise RuntimeError("Unit component head changed while reading")
        return head, identities, result

    last_error = None
    first_head = None
    for _attempt in range(4):
        try:
            current_head, identities, result = traverse()
            if first_head is None:
                first_head = current_head
            elif current_head != first_head:
                raise RuntimeError("Unit component head changed while retrying")
            second_head, second_identities, second_result = traverse()
            if (identities != second_identities or result != second_result
                    or current_head != second_head
                    or registry.resolve_unit(memory, unit) != (handle, owner)):
                raise RuntimeError("Unit component identity changed while reading")
            return result
        except RuntimeError as exc:
            last_error = exc
            if "changed" not in str(exc):
                raise
    raise RuntimeError("Unit component list remained unstable after retries") from last_error


def read_unit_components(memory, registry, owner, names):
    result = {}
    for tag, wrapper, handle, data in read_unit_component_nodes(memory, registry, owner):
        name = names.get(tag)
        if name is not None:
            if not data or memory.read_u64(data + 0x68) != memory.read_u64(owner + 0x90):
                raise RuntimeError("Invalid component unit link")
            if name in result:
                raise RuntimeError("Duplicate built-in unit component")
            result[name] = (wrapper, data)
    return result
