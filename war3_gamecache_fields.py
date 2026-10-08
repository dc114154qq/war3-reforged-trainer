"""Strict, bounded extraction of actual Warcraft III game-cache fields."""

from __future__ import annotations
from dataclasses import dataclass
import hashlib, math, struct, zlib

MAGIC = b"Warcraft III recorded game\x1a\0"
MAX_FILE = 64 * 1024 * 1024
MAX_RAW = 128 * 1024 * 1024
MAX_COUNT = 100_000
MAX_STRING = 8192


class ArchiveFormatError(ValueError):
    pass


def _fold(value):
    return ((value >> 16) ^ (value & 65535)) & 65535


def _checksum(payload, compressed, original, shape):
    header = struct.pack(shape, compressed, original, 0)
    return _fold(zlib.crc32(header)) | (_fold(zlib.crc32(payload)) << 16)


def unpack_container(blob):
    if not isinstance(blob, bytes) or not 68 <= len(blob) <= MAX_FILE:
        raise ArchiveFormatError("存档文件大小无效或超过 64 MB。")
    if not blob.startswith(MAGIC):
        raise ArchiveFormatError("这个文件不是魔兽争霸存档／缓存文件。")
    header, total, version, declared, count = struct.unpack_from("<5I", blob, 28)
    if (
        total != len(blob)
        or version not in (0, 1)
        or not 64 <= header <= min(len(blob), 4096)
        or not 0 < declared <= MAX_RAW
        or not 0 < count <= 65536
    ):
        raise ArchiveFormatError("存档文件头不完整、版本不受支持或长度不一致。")
    crc_at = 64 if version == 1 else 48
    if header < crc_at + 4:
        raise ArchiveFormatError("存档文件头校验信息不完整。")
    copied = bytearray(blob[:header])
    expected = struct.unpack_from("<I", copied, crc_at)[0]
    copied[crc_at : crc_at + 4] = bytes(4)
    if zlib.crc32(copied) & 0xFFFFFFFF != expected:
        raise ArchiveFormatError("存档文件头校验失败，文件可能损坏。")
    matches = []
    for shape in ("<III", "<HHI"):
        try:
            pos = header
            chunks = []
            expanded = 0
            for _ in range(count):
                if pos + struct.calcsize(shape) > len(blob):
                    raise ValueError("short block")
                compressed, original, check = struct.unpack_from(shape, blob, pos)
                pos += struct.calcsize(shape)
                if (
                    not 0 < compressed <= len(blob) - pos
                    or not 0 < original <= 1024 * 1024
                ):
                    raise ValueError("invalid block size")
                payload = blob[pos : pos + compressed]
                pos += compressed
                if check != _checksum(payload, compressed, original, shape):
                    raise ValueError("bad block checksum")
                dec = zlib.decompressobj()
                chunk = dec.decompress(payload, original + 1)
                if len(chunk) != original or dec.unconsumed_tail or dec.unused_data:
                    raise ValueError("bad expanded size")
                chunks.append(chunk)
                expanded += len(chunk)
                if expanded > MAX_RAW:
                    raise ValueError("raw limit")
            if (
                pos != len(blob)
                or not declared <= expanded
                or expanded - declared >= 1024 * 1024
            ):
                raise ValueError("length mismatch")
            raw = b"".join(chunks)
            if any(raw[declared:]):
                raise ValueError("nonzero padding")
            matches.append((raw[:declared], shape))
        except (ValueError, zlib.error, struct.error):
            continue
    if len(matches) != 1:
        raise ArchiveFormatError("存档压缩块校验失败或格式不能唯一识别，未提取数据。")
    raw, shape = matches[0]
    return raw, {
        "container_version": version,
        "block_header": shape,
        "blocks": count,
        "raw_bytes": len(raw),
        "source_sha256": hashlib.sha256(blob).hexdigest(),
    }


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.items = 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ArchiveFormatError("缓存记录不完整，未把残缺记录当作有效字段。")
        value = self.data[self.pos : self.pos + n]
        self.pos += n
        return value

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def count(self, maximum=MAX_COUNT):
        value = self.u32()
        self.items += value
        if value > maximum or self.items > MAX_COUNT:
            raise ArchiveFormatError("缓存记录数量超过读取范围。")
        return value

    def string(self):
        end = self.data.find(
            b"\0", self.pos, min(len(self.data), self.pos + MAX_STRING + 1)
        )
        if end < 0:
            raise ArchiveFormatError("缓存文字没有完整结束标记，未猜测字段名称。")
        raw = self.take(end - self.pos + 1)[:-1]
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return raw.decode("gb18030")
            except UnicodeDecodeError:
                raise ArchiveFormatError("缓存文字编码未识别，未替换或丢失原字节。")


def rawcode(value):
    if value == 0:
        return ""
    text = value.to_bytes(4, "big")
    return (
        text.decode("ascii")
        if all(32 <= byte <= 126 for byte in text)
        else f"0x{value:08X}"
    )


def _unit(reader, layout="reforged"):
    unit_id = reader.u32()
    slots = reader.count(512)
    inventory = []
    for index in range(slots):
        item, charges, flags = reader.u32(), reader.u32(), reader.u32()
        inventory.append(
            {
                "slot": index + 1,
                "item": rawcode(item),
                "charges": charges,
                "raw_flags": flags,
            }
        )
    xp, level_minus_one, points = reader.u32(), reader.u32(), reader.u32()
    proper_name = reader.take(4).hex()
    strength = reader.u32()
    strength_bonus = struct.unpack("<f", reader.take(4))[0]
    agility = reader.u32()
    move_bonus, attack_bonus, agility_bonus = struct.unpack("<3f", reader.take(12))
    intelligence = reader.u32()
    intelligence_bonus = struct.unpack("<f", reader.take(4))[0]
    skills = []
    for _ in range(reader.count(4096)):
        ability = reader.u32()
        secondary = reader.u32() if layout in ("reforged", "modern_skills") else ability
        rank = reader.u32()
        if rank > 100000:
            raise ArchiveFormatError("保存的技能等级不符合结构，未套用错误的英雄布局。")
        skills.append(
            {
                "ability": rawcode(ability),
                "raw_secondary_id": rawcode(secondary),
                "level": rank,
            }
        )
    tail = reader.take(30)
    life, mana, sight = struct.unpack_from("<3f", tail)
    attack1, attack2 = struct.unpack_from("<2i", tail, 16)
    armor = struct.unpack_from("<f", tail, 24)[0]
    extra = []
    if layout in ("reforged", "classic_extension"):
        for _ in range(2):
            records = []
            for _ in range(reader.count(4096)):
                records.append(list(struct.unpack("<3I", reader.take(12))))
            extra.append(records)
    real_values = (
        strength_bonus,
        move_bonus,
        attack_bonus,
        agility_bonus,
        intelligence_bonus,
        life,
        mana,
        sight,
        armor,
    )
    if any(not math.isfinite(x) for x in real_values):
        raise ArchiveFormatError("英雄缓存中的实数字段异常，未显示猜测数值。")
    return {
        "unit_id": rawcode(unit_id),
        "inventory_slots": slots,
        "inventory": inventory,
        "experience": xp,
        "level": level_minus_one + 1,
        "level_minus_one": level_minus_one,
        "unspent_skill_points": points,
        "strength": strength,
        "strength_bonus": strength_bonus,
        "agility": agility,
        "agility_bonus": agility_bonus,
        "agility_move_increment": move_bonus,
        "agility_attack_increment": attack_bonus,
        "intelligence": intelligence,
        "intelligence_bonus": intelligence_bonus,
        "life_increment": life,
        "mana_increment": mana,
        "sight_range": sight,
        "attack_increment_1": attack1,
        "attack_increment_2": attack2,
        "armor_increment": armor,
        "skills": skills,
        "raw_name_indices": proper_name,
        "raw_tail": tail.hex(),
        "raw_extension_lists": extra,
    }


def parse_cache(raw, layout="reforged"):
    reader = Reader(raw)
    reserved = reader.u32()
    cache_count = reader.count(4096)
    fields = []
    caches = []
    for _ in range(cache_count):
        name = reader.string()
        cache_reserved = reader.u32()
        categories = reader.count(4096)
        if not name or len(name) > 1024 or any(ord(ch) < 32 for ch in name):
            raise ArchiveFormatError("缓存名称不符合实际存档结构，未继续套用布局。")
        caches.append(
            {"name": name, "reserved": cache_reserved, "categories": categories}
        )
        for _ in range(categories):
            category = reader.string()
            reserved_types = reader.take(20).hex()
            for kind in ("integer", "real", "boolean", "unit", "string"):
                for _ in range(reader.count()):
                    key = reader.string()
                    offset = reader.pos
                    if kind == "integer":
                        value = reader.i32()
                    elif kind == "real":
                        value = struct.unpack("<f", reader.take(4))[0]
                        if not math.isfinite(value):
                            raise ArchiveFormatError(
                                "缓存实数不是有限数值，未作为正常字段显示。"
                            )
                    elif kind == "boolean":
                        value = reader.u32()
                        if value not in (0, 1):
                            raise ArchiveFormatError(
                                "缓存布尔值不符合格式，未把错位数据当作字段。"
                            )
                        value = bool(value)
                    elif kind == "unit":
                        value = _unit(reader, layout)
                    else:
                        value = reader.string()
                    fields.append(
                        {
                            "cache": name,
                            "category": category,
                            "key": key,
                            "type": kind,
                            "value": value,
                            "raw_offset": offset,
                            "category_reserved": reserved_types,
                        }
                    )
    if reader.pos != len(raw):
        raise ArchiveFormatError("缓存存在尚未识别的额外字段，未宣称完整解析。")
    return {
        "fields": fields,
        "caches": caches,
        "reserved": reserved,
        "complete": True,
        "source_kind": "campaign_cache",
        "field_count": len(fields),
        "unit_layout": layout if any(f["type"] == "unit" for f in fields) else None,
    }


def extract_cache_file_bytes(blob):
    raw, metadata = unpack_container(blob)
    matches = []
    errors = []
    for layout in ("reforged", "classic", "modern_skills", "classic_extension"):
        try:
            matches.append(parse_cache(raw, layout))
        except ArchiveFormatError as exc:
            errors.append(str(exc))
    if not matches:
        raise ArchiveFormatError(errors[0])
    if any(matches[0]["fields"] != match["fields"] for match in matches[1:]):
        raise ArchiveFormatError(
            "英雄缓存结构不能唯一确定，未把候选结果当作已识别数据。"
        )
    result = matches[0]
    result["metadata"] = metadata
    return result


def extract_save_file_bytes(blob):
    """Read framed embedded cache blocks, not arbitrary matching strings."""
    raw, metadata = unpack_container(blob)
    token = b"Campaigns.w3v\0"
    pos = 0
    results = []
    while True:
        found = raw.find(token, pos)
        if found < 0:
            break
        pos = found + len(token)
        if found < 40 or raw[found - 40 : found - 36] != b"espi":
            continue
        payload_length = struct.unpack_from("<I", raw, found - 36)[0]
        cache_size = payload_length - 32 - len(token)
        if not 8 <= cache_size <= MAX_RAW or pos + cache_size > len(raw):
            continue
        payload = raw[pos : pos + cache_size]
        if len(results) >= 64:
            raise ArchiveFormatError(
                "存档包含超过 64 段战役缓存，请载入后读取当前英雄，未把部分记录当作全部结果。"
            )
        # Reuse exactly the same unit/layout checks as a standalone cache.
        matches = []
        for layout in ("reforged", "classic", "modern_skills", "classic_extension"):
            try:
                matches.append(parse_cache(payload, layout))
            except ArchiveFormatError:
                continue
        if not matches:
            raise ArchiveFormatError(
                "存档中的战役缓存已定位，但英雄记录格式尚未识别；未显示猜测数据。"
            )
        if any(m["fields"] != matches[0]["fields"] for m in matches[1:]):
            raise ArchiveFormatError("存档中的英雄缓存布局有歧义，未提取候选结果。")
        result = matches[0]
        result["embedded_offset"] = pos
        result["embedded_length"] = cache_size
        results.append(result)
        pos += cache_size
    if not results:
        raise ArchiveFormatError(
            "这个整局存档中没有找到可确认的战役继承缓存。可载入存档后读取当前选中英雄。"
        )
    combined = {
        "fields": [],
        "caches": [],
        "complete": True,
        "source_kind": "embedded_campaign_cache",
        "metadata": metadata,
        "embedded_caches": [],
    }
    for result in results:
        combined["fields"].extend(result["fields"])
        combined["caches"].extend(result["caches"])
        combined["embedded_caches"].append(
            {
                key: value
                for key, value in result.items()
                if key not in ("fields", "caches")
            }
        )
    combined["field_count"] = len(combined["fields"])
    combined["notice"] = (
        "提取的是保存时的战役继承缓存；当前英雄的即时状态请载入存档后读取。"
    )
    return combined
