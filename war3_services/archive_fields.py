"""Read-only campaign cache files and session-bound selected-hero snapshots."""

from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import csv, io, json, os

from war3_gamecache_fields import (
    ArchiveFormatError,
    MAX_FILE,
    extract_cache_file_bytes,
    extract_save_file_bytes,
    rawcode,
)
from war3_save_codes import SaveExtractionError
from war3_services.save_extraction import _atomic_new_file, documents_directory

EQUIPMENT_NAMES = (
    "头部",
    "胸部",
    "手套",
    "靴子",
    "戒指",
    "戒指 2",
    "主手",
    "副手",
    "饰品",
)


def find_archive_files(root=None, *, cancel=None, max_files=5000):
    root = Path(root) if root else documents_directory() / "Warcraft III"
    if not root.is_dir():
        raise SaveExtractionError(
            "未找到战役存档目录，请选择保存 .w3v 或 .w3z 文件的目录。"
        )
    files = []
    warnings = []
    complete = True

    def onerror(exc):
        warnings.append({"source": str(exc.filename), "reason": str(exc)})

    for directory, dirs, names in os.walk(root, followlinks=False, onerror=onerror):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
        for name in names:
            if cancel is not None and cancel.is_set():
                complete = False
                break
            path = Path(directory) / name
            if path.suffix.lower() not in (".w3v", ".w3z") or path.is_symlink():
                continue
            if len(files) >= max_files:
                complete = False
                break
            try:
                stat = path.stat()
                files.append(
                    {
                        "path": str(path),
                        "name": name,
                        "bytes": stat.st_size,
                        "modified_ns": stat.st_mtime_ns,
                    }
                )
            except OSError as exc:
                warnings.append({"source": str(path), "reason": str(exc)})
        if not complete:
            break
    files.sort(key=lambda f: f["modified_ns"], reverse=True)
    return {"files": files, "complete": complete and not warnings, "warnings": warnings}


def read_archive_file(path):
    path = Path(path)
    if path.suffix.lower() not in (".w3v", ".w3z") or not path.is_file():
        raise SaveExtractionError("请选择魔兽争霸战役缓存 .w3v 或游戏存档 .w3z 文件。")
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if before.st_size > MAX_FILE:
                raise SaveExtractionError(
                    "所选存档超过 64 MB，请先载入该存档，再读取当前选中英雄。"
                )
            blob = stream.read(MAX_FILE + 1)
            after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns) != (
            after.st_size,
            after.st_mtime_ns,
        ) or len(blob) != before.st_size:
            raise SaveExtractionError(
                "游戏正在更新这个存档文件，请等保存结束后重新读取。"
            )
        result = (
            extract_cache_file_bytes
            if path.suffix.lower() == ".w3v"
            else extract_save_file_bytes
        )(blob)
        result.update(
            source=str(path),
            source_modified_ns=before.st_mtime_ns,
            captured_at=datetime.now(timezone.utc).isoformat(),
        )
        result["heroes"] = [
            {
                "cache": field["cache"],
                "category": field["category"],
                "key": field["key"],
                **field["value"],
            }
            for field in result["fields"]
            if field["type"] == "unit"
        ]
        return result
    except ArchiveFormatError as exc:
        error = SaveExtractionError(str(exc))
        error.__cause__ = exc
        raise error
    except OSError as exc:
        error = SaveExtractionError("存档文件未能读取，请检查文件路径和占用情况。")
        error.__cause__ = exc
        raise error


def _inventory_section(count, index):
    if count == 45:
        if index < 6:
            return "经典物品栏", index + 1
        if index < 36:
            return "扩展背包", index - 5
        return "装备栏", EQUIPMENT_NAMES[index - 36]
    if count == 6:
        return "经典物品栏", index + 1
    return "保存物品栏", index + 1


def display_rows(result):
    rows = []
    for field in result.get("fields", ()):
        scope = f"{field['cache']} / {field['category']}"
        value = field["value"]
        key = field["key"]
        if field["type"] != "unit":
            rows.append((scope, key, field["type"], value))
            continue
        labels = {
            "unit_id": "单位 ID",
            "level": "保存等级",
            "experience": "经验",
            "unspent_skill_points": "未用技能点",
            "strength": "基础力量",
            "agility": "基础敏捷",
            "intelligence": "基础智力",
            "strength_bonus": "力量加成",
            "agility_bonus": "敏捷加成",
            "intelligence_bonus": "智力加成",
            "life_increment": "生命增量",
            "mana_increment": "法力增量",
            "armor_increment": "护甲增量",
            "agility_attack_increment": "保存的敏捷攻速增量",
        }
        for name, label in labels.items():
            if name in value:
                rows.append((scope, key + " / " + label, "hero", value[name]))
        for index, item in enumerate(value.get("inventory", ())):
            if not item.get("item"):
                continue
            section, slot = _inventory_section(value["inventory_slots"], index)
            rows.append(
                (
                    scope,
                    f"{key} / {section} {slot}",
                    "item",
                    f"{item['item']}；充能 {item['charges']}",
                )
            )
        for skill in value.get("skills", ()):
            if skill.get("ability") and skill.get("level"):
                rows.append(
                    (
                        scope,
                        f"{key} / 技能 {skill['ability']}",
                        "ability",
                        skill["level"],
                    )
                )
    for hero in result.get("live_heroes", ()):
        scope = f"当前英雄 / {hero['unit_id']}"
        if hero.get("player_id") is not None:
            scope += f" / 玩家 {hero['player_id']}"
        for field in hero["fields"]:
            rows.append((scope, field["label"], field["type"], field["value"]))
        for item in hero["items"]:
            if item["item"]:
                rows.append(
                    (
                        scope,
                        f"{item['section']} {item['slot']}",
                        "item",
                        f"{item['item']}；充能 {item['charges']}",
                    )
                )
    return tuple(rows)


def export_archive_result(path, result):
    path = Path(path)
    if not result or not (result.get("fields") or result.get("live_heroes")):
        raise SaveExtractionError("尚未提取到存档字段或英雄，请先读取文件或当前英雄。")
    if path.suffix.lower() == ".csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(("来源／章节", "字段", "类型", "值"))
        for row in display_rows(result):
            # CSV cells are data, including attacker-controlled map/key names.
            writer.writerow(
                tuple(
                    "'" + str(cell)
                    if isinstance(cell, str)
                    and cell.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                    else cell
                    for cell in row
                )
            )
        data = stream.getvalue().encode("utf-8-sig")
    elif path.suffix.lower() == ".json":
        data = (
            json.dumps(
                {"format": "war3-archive-fields", "schema_version": 1, **result},
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    else:
        raise SaveExtractionError("导出文件请使用 .json 或 .csv 后缀。")
    _atomic_new_file(path, data)
    return str(path)


def read_current_heroes(host):
    from war3_external_backend import ExternalMemoryBackend
    from war3_game_session import session_scope

    session = host._game_session
    engine = host._engine_instance_24268()
    result = {
        "source_kind": "loaded_game_snapshot",
        "source": "当前游戏中选中英雄",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "live_heroes": [],
        "warnings": [],
        "complete": True,
    }
    if (session.pid, session.hwnd) != (host.pid, host.hwnd):
        raise SaveExtractionError("游戏进程或窗口已变化，请先重新连接后再读取英雄。")
    with session.lock:
        with host._session_memory_factory(host.pid) as memory:
            session.prepare(memory)
        with session_scope(session):
            with host._session_memory_factory(host.pid) as memory:
                refs = ExternalMemoryBackend(session).selected_units(memory)
            if not refs:
                raise SaveExtractionError("请先载入游戏存档，并选中要提取的英雄。")
            if len(refs) > 24:
                raise SaveExtractionError(
                    "一次最多读取 24 个选中单位，请减少选择数量。"
                )
            bindings = engine.bind_unit_refs(tuple(refs))
            progress = engine.hero_progress()
            heroes = {row["handle"]: row for row in progress["rows"]}
            inventory = engine.item_batch(action=0) if heroes else {"rows": []}
            candidates = {
                candidate.handle: candidate
                for candidate, _ in host._selected_candidates_snapshot(None)
            }
            for native, ref in bindings:
                if native.value not in heroes:
                    continue
                candidate = candidates.get(ref.handle.value)
                if (
                    candidate is None
                    or candidate.unit_address != ref.address.value
                    or candidate.unit_type_id != ref.rawcode
                ):
                    raise SaveExtractionError(
                        "选中单位在提取期间发生变化，请重新读取。"
                    )
                _, candidate, fields = host.read_unit_fields_by_identity(
                    candidate.handle, candidate.owner_address, candidate.unit_address
                )
                for warning in getattr(host, "_unit_field_warnings", ()):
                    result["complete"] = False
                    result["warnings"].append(
                        {
                            "unit": rawcode(ref.rawcode),
                            "section": "英雄属性",
                            "reason": str(warning),
                        }
                    )
                player_fields = [
                    field for field in fields if field.key in ("owner_id", "player_id")
                ]
                hero = {
                    "unit_id": rawcode(ref.rawcode),
                    "player_id": int(player_fields[0].value) if player_fields else None,
                    "level": heroes[native.value]["level"],
                    "fields": [],
                    "items": [],
                }
                for field in fields:
                    if field.value_type in ("ptr", "u64") or any(
                        term in field.key for term in ("address", "handle", "pointer")
                    ):
                        continue
                    if not isinstance(field.value, (str, int, float, bool)):
                        continue
                    hero["fields"].append(
                        {
                            "key": field.key,
                            "label": field.label,
                            "type": field.value_type,
                            "value": field.value,
                            "note": getattr(field, "note", ""),
                        }
                    )
                # The ordinary inventory snapshot includes all selected units;
                # filter by the immutable native binding, never by rawcode alone.
                item_rows = [
                    row for row in inventory["rows"] if row["handle"] == native.value
                ]
                if len(item_rows) != 1 or item_rows[0]["rawcode"] != ref.rawcode:
                    raise SaveExtractionError(
                        "经典物品栏的单位身份不一致，请重新读取。"
                    )
                for index, item in enumerate(item_rows[0]["before"]):
                    hero["items"].append(
                        {
                            "section": "经典物品栏",
                            "slot": index + 1,
                            "item": rawcode(item["rawcode"]),
                            "charges": item["charges"],
                        }
                    )
                try:
                    extension = host.extension_snapshot_24268(native.value)
                    if extension["target_unit"] != native.value:
                        raise SaveExtractionError("扩展背包的单位身份已变化。")
                    for section, rows in (
                        ("扩展背包", extension["bag"]),
                        ("装备栏", extension["equipment"]),
                    ):
                        for item in rows:
                            slot = (
                                EQUIPMENT_NAMES[item["slot"]]
                                if section == "装备栏"
                                else item["slot"] + 1
                            )
                            hero["items"].append(
                                {
                                    "section": section,
                                    "slot": slot,
                                    "item": rawcode(item["rawcode"]),
                                    "charges": item["charges"],
                                }
                            )
                    hero["talent_abilities"] = {
                        rawcode(code): level
                        for code, level in extension["abilities"].items()
                        if level > 0
                    }
                except Exception as exc:
                    result["complete"] = False
                    result["warnings"].append(
                        {
                            "unit": hero["unit_id"],
                            "section": "扩展背包／装备／天赋",
                            "reason": str(exc),
                        }
                    )
                result["live_heroes"].append(hero)
            with host._session_memory_factory(host.pid) as memory:
                registry, _, _ = session.prepare(memory)
                for ref in refs:
                    session.resolve(memory, registry, ref)
            result["game_version"] = session.profile.data["game_version"]
            result["adapter_id"] = session.profile.id
            result["skipped_units"] = len(bindings) - len(result["live_heroes"])
    if not result["live_heroes"]:
        raise SaveExtractionError("选中单位中没有英雄，请选择英雄后重新读取。")
    result["notice"] = (
        "这是载入存档后当前英雄的读取快照，不会修改游戏，也不自动恢复英雄。"
    )
    return result
