"""Failure-atomic, additive map scripts. Original campaign/map is never written."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import traceback
import uuid

from war3_mpq import Archive, canonical_name, normalize_classic_header
from war3_map_objects import object_records
from war3_object_tables import DefinitionError, campaign_maps, map_data_mode, parse_slk
from war3_jass_parser import boundaries, inject, tokens
from war3_map_script_runtime import PRESETS
from war3_huolong_runtime import generate, usage, REVISION, SOURCE_SHA256, configuration
from war3_huolong_catalog import catalogue_entries
from war3_script_features import ScriptOptions, PROTECTED_ABILITIES, PROTECTED_ITEMS
from war3_script_validation import check_script
from war3_services.map_catalog import scan_map_catalog, baseline
# Reuse the existing verified archive primitives without changing the old
# definition algorithm or invoking its definition merge for a script-only job.
from war3_services.extension_definitions import (
    Journal, file_hash, _members, _neutral, _fingerprints, _verify,
    _identify_archive_names, prepare_extension_definitions, definition_pack,
)

MARKER = 'war3trainer\\manifest.json'
ORIGINAL = 'war3trainer\\original.j'
CATALOGUE = 'war3trainer\\catalogue.json'


@dataclass(frozen=True)
class ScriptResult:
    source: str
    output: str
    report_path: str
    log_path: str
    chapter_count: int
    changed_chapters: int
    added_entries: int
    source_sha256: str
    output_sha256: str
    usage_path: str
    command_prefix: str
    combined: bool


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _prefix(raw):
    ids = {t.value for t in tokens(raw) if t.kind == 'identifier'}
    for index in range(100):
        candidate = 'MX'+sha(raw+str(index).encode())[:8]+'_'
        if not any(name.startswith(candidate.encode()) for name in ids):
            return candidate
    raise DefinitionError('章节脚本名称冲突过多，已停止添加。')


def _context(catalogue, scope, mode):
    stock = baseline(mode)
    known = {kind: set(stock[kind]) for kind in ('item','unit','ability')}
    protected_items, protected_abilities = set(PROTECTED_ITEMS), set(PROTECTED_ABILITIES)
    manifest, _ = definition_pack()
    protected_items.update(manifest['critical_items'])
    protected_abilities.update(manifest['critical_abilities'])
    levels = {code: int(stock['ability'].get(code, {}).get('levels') or 3)
              for codes in PRESETS.values() for code in codes}
    # Shared modifications are applied before the chapter's overrides.
    rows = [row for row in catalogue['rows'] if row['scope'] == '战役共用']
    rows += [row for row in catalogue['rows'] if row['scope'] == scope]
    children = {'ability':{}, 'item':{}}
    for row in rows:
        if row['kind'] in children:
            children[row['kind']].setdefault(row['base'], []).append(row['rawcode'])
    def inherit(kind, protected):
        pending = list(protected)
        while pending:
            for code in children[kind].get(pending.pop(), ()):
                if code not in protected:
                    protected.add(code)
                    pending.append(code)
    inherit('ability', protected_abilities)
    inherit('item', protected_items)
    for row in rows:
        if row['kind'] not in known:
            continue
        known[row['kind']].add(row['rawcode'])
        for change in row['changes']:
            if row['kind'] == 'item' and change['field'].casefold() in ('iabi','abillist'):
                value=change['value']
                values=value if isinstance(value,list) else [value]
                abilities = {code.strip() for part in values for code in str(part).split(',')}
                if protected_abilities.intersection(abilities):
                    protected_items.add(row['rawcode'])
            if row['kind'] == 'ability' and change['field'] == 'alev':
                levels[row['rawcode']] = int(change['value'])
    inherit('item', protected_items)
    # Definition completion may introduce control abilities absent from the
    # original chapter. Excluding them keeps the generic payload identical in
    # either composition order and prevents it from managing those controls.
    known['item'].difference_update(protected_items)
    known['ability'].difference_update(protected_abilities)
    inventory={code for code,fields in stock['ability'].items() if fields.get('code')=='AInv'}
    inherit('ability',inventory)
    known['ordinary_inventory']=inventory
    return known, protected_items, protected_abilities, levels


def _upgrades(archive, prefix):
    result=set()
    for stem in (prefix,prefix+'Skin'):
        raw=archive.read(stem+'.w3q',optional=True)
        if raw is not None:
            result.update(r['rawcode'] for r in object_records(raw,extended=True))
    return result


def _patch_chapter(path, scope, catalogue, options, journal, checks):
    journal.check()
    with Archive(path) as archive:
        archive.identify_names((MARKER, ORIGINAL, CATALOGUE))
        _identify_archive_names(archive, journal)
        members = _members(archive, journal)
        metadata = map_data_mode(archive.read('war3map.w3i'))
        if metadata['script_language'] != 0:
            raise DefinitionError('本次功能只支持 JASS 地图；该章节使用 Lua，未修改原文件。')
        scripts = [(name, _neutral(members, name)) for name in ('war3map.j','scripts\\war3map.j')]
        scripts = [(name, member) for name, member in scripts if member is not None]
        if len(scripts) != 1:
            raise DefinitionError('章节没有唯一 JASS 脚本，无法可靠确定游戏入口。')
        name, member = scripts[0]
        current = archive.read(member)
        marker_member, original_member = _neutral(members, MARKER), _neutral(members, ORIGINAL)
        if bool(marker_member) != bool(original_member):
            raise DefinitionError('章节中的旧脚本处理记录不完整，请从原图重新生成。')
        old_marker = None
        if marker_member:
            marker_raw = archive.read(marker_member)
            if len(marker_raw) > 65536:
                raise DefinitionError('章节中的旧脚本处理记录大小异常。')
            old_marker = json.loads(marker_raw)
            original = archive.read(original_member)
            if (old_marker.get('schema') != 1 or old_marker.get('module') != 'mx-map-tools' or
                    old_marker.get('script') != name or old_marker.get('originalSha256') != sha(original) or
                    old_marker.get('patchedSha256') != sha(current)):
                raise DefinitionError('添加功能后章节脚本又被改动，不能自动叠加。请从原图重新生成。')
        else:
            original = current
        parsed = boundaries(original)
        if any(t.kind=='identifier' and t.value==b'hke_z09Z' for t in parsed['tokens']):
            raise DefinitionError('该章节已包含经典火龙 HKE 脚本，请使用未注入火龙的原图，避免两套菜单重复执行。')
        known, protected_items, protected_abilities, levels = _context(catalogue, scope, metadata['mode'])
        _, pack_files = definition_pack()
        known['upgrade'] = set(parse_slk(pack_files['baseline/'+metadata['mode']+'/UpgradeData.slk']).rows)
        known['upgrade'].update(catalogue.get('shared_upgrades', ()))
        known['upgrade'].update(_upgrades(archive,'war3map'))
        known['catalogue'] = catalogue_entries(catalogue, scope, metadata['mode'], known,
                                               protected_items, protected_abilities)
        catalogue_raw = json.dumps(dict(rows=known['catalogue'],gold_mines=known['gold_mines']),
            ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
        catalogue_member = _neutral(members,CATALOGUE)
        prefix = _prefix(original)
        globals_code, functions = generate(options, prefix, known, protected_items=protected_items,
                                             protected_abilities=protected_abilities, levels=levels)
        journal.event('script_baseline_check', name=scope)
        original_check = check_script(original, checks, label=scope+'（原始脚本）', cancel=journal.cancel)
        # Original HKE uses classic Blizzard.j wrappers as well as common.j.
        minimal = b'globals\nendglobals\nfunction main takes nothing returns nothing\nendfunction\n'
        payload = inject(minimal, globals_code, functions, prefix+'Boot')
        payload_check = check_script(payload, checks, label=scope+'（独立功能脚本）', library='classic',
                                     cancel=journal.cancel, include_blizzard=True)
        patched = inject(original, globals_code, functions, prefix+'Boot')
        journal.event('script_compile', name=scope, library=original_check['library'])
        patched_check = check_script(patched, checks, label=scope+'（添加后脚本）',
                                     library=original_check['library'], cancel=journal.cancel)
        marker = dict(schema=1, module='mx-map-tools', revision=REVISION, script=name,
            originalSha256=sha(original), patchedSha256=sha(patched), options=configuration(options),
            runtimePrefix=prefix, independentOfTrainer=True, runtime='HKE 1.25B',
            originalPayloadSha256=SOURCE_SHA256,ordinaryInventoryAbilities=sorted(known['ordinary_inventory']),
            catalogueSha256=sha(catalogue_raw))
        marker_raw = json.dumps(marker, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode('utf-8')
        if old_marker == marker and patched == current and catalogue_member and archive.read(catalogue_member)==catalogue_raw:
            return dict(name=scope, changed=False, already_added=True, metadata=metadata,
                original_check=original_check, payload_check=payload_check, patched_check=patched_check,
                command_prefix='-', script=name, independent_of_trainer=True)
        before = _fingerprints(archive, members, journal)
        plan = {name: (patched, member), MARKER: (marker_raw, marker_member), ORIGINAL: (original, original_member),
                CATALOGUE: (catalogue_raw,catalogue_member)}
    header_repair = normalize_classic_header(path, names=(key[0] for key in before),
        progress=lambda s,d:journal.event(s,**d), check=journal.check)
    with Archive(path, writable=True) as archive:
        archive.identify_names((MARKER, ORIGINAL, CATALOGUE))
        _identify_archive_names(archive, journal)
        archive.reserve(sum(member is None for raw, member in plan.values()), progress=lambda s,d:journal.event(s,**d),check=journal.check)
        for filename, (raw, old) in plan.items():
            journal.event('script_write', path=filename, bytes=len(raw), original_flags=old.flags if old else None)
            archive.write(filename, raw, original=old)
        archive.flush()
        archive.compact(progress=lambda s,d:journal.event(s,**d))
    expected = {(filename.casefold(), old.locale if old else 0):sha(raw) for filename,(raw,old) in plan.items()}
    _verify(path, before, expected, journal)
    with Archive(path) as archive:
        readback = archive.read(name)
        assert sha(readback) == sha(patched)
        readback_check = check_script(readback, checks, label=scope+'（归档读回）',
            library=original_check['library'], cancel=journal.cancel)
    return dict(name=scope, changed=True, already_added=False, metadata=metadata,
        original_check=original_check, payload_check=payload_check, patched_check=patched_check,
        readback_check=readback_check, command_prefix='-', script=name,
        original_sha256=sha(original), script_sha256=sha(patched),
        protected_items=sorted(protected_items), protected_abilities=sorted(protected_abilities),
        ordinary_inventory_abilities=sorted(known['ordinary_inventory']),
        menu_catalogue={kind:sum(r['kind']==kind for r in known['catalogue']) for kind in ('item','ability','unit','upgrade')},
        catalogue_sha256=sha(catalogue_raw), archive_header_repair=header_repair,
        independent_of_trainer=True)


def prepare_map_script(source, output_folder, *, options=None, combined=False, progress=None, cancel=None):
    options = options if type(options) is ScriptOptions else ScriptOptions.parse(options)
    if type(combined) is not bool:
        raise ValueError('组合处理设置必须为布尔值。')
    source = Path(str(source).strip().strip('"')).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.casefold() not in ('.w3n','.w3x','.w3m'):
        raise DefinitionError('请选择 w3n 战役、w3x 或 w3m 地图。')
    if source.stat().st_size > 8*1024**3:
        raise DefinitionError('文件超过 8 GB，已停止处理。')
    folder = Path(output_folder).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    run = folder/(source.stem[:60]+'-地图功能-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    run.mkdir(exist_ok=False)
    checks = run/'脚本检查'
    journal = Journal(run/'处理日志.jsonl', progress, cancel or threading.Event())
    pending = run/'未完成.tmp'
    current_chapter = ''
    try:
        journal.event('source_hash_begin', source=str(source), log_path=str(journal.path))
        initial = (source.stat().st_size, source.stat().st_mtime_ns)
        source_hash = file_hash(source)
        journal.event('start', source=str(source), source_sha256=source_hash, combined=combined,
                      revision=REVISION, options=options.data(), independent_of_trainer=True)
        with tempfile.TemporaryDirectory(prefix='war3-map-scripts-') as temporary:
            work = Path(temporary)
            staged = work/('source'+source.suffix)
            shutil.copyfile(source, staged)
            if file_hash(staged) != source_hash:
                raise DefinitionError('输入文件复制校验失败。')
            definition_report = None
            if combined:
                journal.event('definitions_begin')
                def forward(stage, data):
                    journal.event('definitions_'+stage, **data)
                result = prepare_extension_definitions(staged, work/'definitions', progress=forward, cancel=journal.cancel)
                definition_report = json.loads(Path(result.report_path).read_text(encoding='utf-8'))
                shutil.copyfile(result.log_path, run/'背包定义处理日志.jsonl')
                shutil.copyfile(result.output, staged)
                journal.event('definitions_complete', chapters=result.chapter_count)
            journal.event('catalogue_begin')
            catalogue = scan_map_catalog(staged, cancel=journal.cancel,
                progress=lambda stage,data:journal.event('catalogue_'+stage,**data))
            if catalogue['warnings']:
                exc = DefinitionError('部分章节对象定义未能完整读取，已停止添加脚本。')
                exc.user_details = catalogue['warnings']
                raise exc
            reports = []
            if source.suffix.casefold() == '.w3n':
                with Archive(staged) as archive:
                    catalogue['shared_upgrades'] = _upgrades(archive,'war3campaign')
                    referenced = campaign_maps(archive.read('war3campaign.w3f'))
                    archive.identify_names(referenced)
                    _identify_archive_names(archive, journal)
                    members = _members(archive, journal)
                    chapters = [m for m in members.values() if m.name.casefold().endswith(('.w3x','.w3m'))]
                    if not chapters or len(chapters) > 1000:
                        raise DefinitionError('战役章节数量为空或超过范围。')
                    if not {canonical_name(n).casefold() for n in referenced} <= {m.name.casefold() for m in chapters}:
                        raise DefinitionError('战役目录引用的章节不完整，已停止处理。')
                    before = _fingerprints(archive, members, journal)
                    for index, member in enumerate(chapters):
                        chapter = work/('chapter-'+str(index)+'.w3x')
                        chapter.write_bytes(archive.read(member))
                changed = []
                for index, member in enumerate(chapters):
                    current_chapter = member.name
                    journal.event('chapter_begin', index=index+1, total=len(chapters), name=member.name)
                    chapter = work/('chapter-'+str(index)+'.w3x')
                    report = _patch_chapter(chapter, member.name, catalogue, options, journal, checks)
                    reports.append(report)
                    if report['changed']:
                        changed.append((member, chapter))
                    journal.event('chapter_verified', name=member.name, changed=report['changed'])
                expected = {}
                if changed:
                    normalize_classic_header(staged, names=(key[0] for key in before),
                        progress=lambda s,d:journal.event(s,**d), check=journal.check)
                    with Archive(staged, writable=True) as archive:
                        archive.identify_names(referenced)
                        _identify_archive_names(archive, journal)
                        for member, chapter in changed:
                            journal.event('replace_chapter', name=member.name, original_flags=member.flags)
                            archive.write(member.name, chapter.read_bytes(), original=member)
                            expected[(member.name.casefold(), member.locale)] = file_hash(chapter)
                        archive.flush()
                        archive.compact(progress=lambda s,d:journal.event(s,**d))
                _verify(staged, before, expected, journal)
            else:
                current_chapter = source.name
                journal.event('chapter_begin', index=1, total=1, name=source.name)
                scope = next(s for s in catalogue['scopes'] if s != '战役共用')
                for row in catalogue['rows']:
                    if row['scope'] == scope:
                        row['scope'] = source.name
                reports.append(_patch_chapter(staged, source.name, catalogue, options, journal, checks))
                journal.event('chapter_verified', name=source.name, changed=reports[-1]['changed'])
            journal.check()
            if initial != (source.stat().st_size, source.stat().st_mtime_ns) or source_hash != file_hash(source):
                raise DefinitionError('处理期间输入文件发生变化，已停止输出。')
            output_hash = file_hash(staged)
            shutil.copyfile(staged, pending)
            if file_hash(pending) != output_hash:
                raise DefinitionError('输出副本复制校验失败。')
            destination = run/(source.stem+('_背包定义与地图功能' if combined else '_地图功能')+source.suffix)
            report_path = run/'处理报告.json'
            usage_path = run/'游戏内功能使用说明.txt'
            usage_path.write_text(usage(options), encoding='utf-8-sig')
            report = dict(schema=1, revision=REVISION, source=str(source), sourceSha256=source_hash,
                output=str(destination), outputSha256=output_hash, options=configuration(options),
                combined=combined, definitions=definition_report, chapters=reports,
                verification=dict(source_unchanged=True, member_hashes_and_flags_verified=True,
                    scripts_typechecked=True, payload_checked_with_classic_interface=True,
                    independent_of_trainer=True, gameplay_tested=False, old_saves_updated=False))
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            journal.event('verified', output=str(destination), report_path=str(report_path), usage_path=str(usage_path))
            os.fsync(journal.stream.fileno())
            journal.check()
            os.replace(pending, destination)
        return ScriptResult(str(source), str(destination), str(report_path), str(journal.path), len(reports),
            sum(r['changed'] for r in reports), len(reports), source_hash, output_hash,
            str(usage_path), '-', combined)
    except Exception as exc:
        pending.unlink(missing_ok=True)
        try:
            journal.stream.write(json.dumps(dict(stage='failed', chapter=current_chapter,
                exception=repr(exc), traceback=traceback.format_exc(), output_published=False), ensure_ascii=False)+'\n')
            journal.stream.flush()
        except (OSError, ValueError):
            pass
        if isinstance(exc, InterruptedError) or journal.cancel.is_set():
            error = InterruptedError('处理已停止，原文件已保留。')
        else:
            error = DefinitionError((f'处理章节“{current_chapter}”时：' if current_chapter else '')+str(exc))
        error.diagnostic_log_path = str(journal.path)
        error.user_title = '地图功能脚本未能完成'
        error.user_details = getattr(exc, 'user_details', None) or [dict(scope=current_chapter or source.name,
            file='地图功能脚本', message=str(exc), impact='未输出最终副本，原文件可继续使用。')]
        raise error from exc
    finally:
        journal.close()
