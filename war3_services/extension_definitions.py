"""Offline, additive 3.0 object definitions; archive originals are never edited."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
import hashlib, json, os, re, shutil, sys, tempfile, time, traceback, uuid, zipfile
from war3_mpq import Archive, MpqError, STORAGE_FLAGS, canonical_name, unknown_member_name
from war3_jass_validation import check_function_order
from war3_object_tables import (DefinitionError, parse_slk, parse_profile, merge_slk,
                                merge_profile, map_data_mode, campaign_maps, object_ids, _value,
                                validate_game_slk, make_extension_versions_compatible)

PACK_SHA256='92fb7ef32f24d0b218124034c42642490a1c251b843e9511ab531a12bd7c03f1'
PROCESSING_REVISION='extension-script-order-compact-v5-20261024'
META={'(listfile)','(attributes)'}
OBJECT_FILES=(('w3a',True),('w3t',False),('w3u',False),('w3h',False),('w3q',True))


@dataclass(frozen=True)
class DefinitionResult:
    source: str
    output: str
    report_path: str
    log_path: str
    chapter_count: int
    changed_chapters: int
    added_entries: int
    source_sha256: str
    output_sha256: str


def file_hash(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(4*1024*1024),b''):result.update(chunk)
    return result.hexdigest()


@lru_cache(maxsize=1)
def definition_pack():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    path=root/'assets/extension-definitions-v1.zip'
    if not path.is_file() or file_hash(path)!=PACK_SHA256:
        raise DefinitionError('背包定义资料缺失或校验失败，请重新下载完整修改器。')
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist()
        if len(infos)>256 or sum(i.file_size for i in infos)>128*1024*1024:
            raise DefinitionError('背包定义资料大小异常。')
        if len({i.filename for i in infos})!=len(infos):raise DefinitionError('背包定义资料存在重复文件。')
        files={i.filename:archive.read(i) for i in infos}
    manifest=json.loads(files.pop('manifest.json'))
    if manifest.get('schema')!=1 or set(files)!=set(manifest['files']):
        raise DefinitionError('背包定义资料结构异常。')
    for name, raw in files.items():
        expected=manifest['files'][name]
        if len(raw)!=expected['bytes'] or hashlib.sha256(raw).hexdigest()!=expected['sha256']:
            raise DefinitionError('背包定义资料内容校验失败。')
    return manifest,files


class Journal:
    def __init__(self,path,progress,cancel):
        self.path=path;self.stream=path.open('x',encoding='utf8',buffering=1)
        self.progress=progress;self.cancel=cancel;self.sequence=0
    def check(self):
        if self.cancel is not None and self.cancel.is_set():raise DefinitionError('处理已停止，原文件已保留。')
    def event(self,stage,**data):
        self.check();self.sequence+=1
        self.stream.write(json.dumps(dict(sequence=self.sequence,time=time.strftime('%Y-%m-%d %H:%M:%S'),
                                          stage=stage,**data),ensure_ascii=False)+'\n')
        self.stream.flush()
        if self.progress is not None:self.progress(stage,data)
    def close(self):self.stream.close()


def _members(archive,journal=None):
    members=archive.members();result={}
    for member in members:
        key=(member.name.casefold(),member.locale)
        if key in result:
            if key[0] in META:
                # Editors sometimes leave older listfile/attribute entries.
                # These are library-maintained metadata, excluded from payload
                # fingerprints. Keep strict ambiguity checks for all game files.
                if journal:journal.event('archive_duplicate_metadata',archive=archive.path.name,
                    name=member.name,locale=member.locale,kept_block=result[key].block_index,
                    duplicate_block=member.block_index)
                continue
            raise DefinitionError('地图归档存在重复文件或大小写冲突：'+member.name)
        if member.name.casefold()=='(signature)':raise DefinitionError('该地图带有归档签名，请单独处理这份地图。')
        result[key]=member
    return result


def _reference_names(raw):
    """Bounded filename hints from stored object/script/model strings.

    Hints never rename a member: StormLib accepts only exact existing hashes.
    JASS escapes backslashes, and Warcraft accepts .mdl references for .mdx.
    """
    names=set()
    suffix=re.compile(rb'\.(?:blp|tga|dds|mdx|mdl|wav|mp3|ogg|flac|fdf|toc|txt|slk|lua|j)(?=$|[\s"\',;])',re.I)
    for match in re.finditer(rb'[\x20-\x7e\x80-\xff]{4,1024}',raw):
        text=match.group().replace(b'\\\\',b'\\')
        for end in suffix.finditer(text):
            segment=text[:end.end()]
            starts=[0]+[i+1 for i,char in enumerate(segment) if char in b'"\'=,;([])\t']
            for start in starts:
                value=segment[start:].strip()
                if not 4<=len(value)<260:continue
                if any(char in value for char in (b'"',b"'",b'=',b',',b';')):continue
                try:name=canonical_name(value.decode('utf8'))
                except (UnicodeError,MpqError):continue
                names.add(name)
                if name.lower().endswith('.mdl'):names.add(name[:-4]+'.mdx')
                if name.lower().endswith(('.mdl','.mdx')) and not name[:-4].lower().endswith('_portrait'):
                    names.add(name[:-4]+'_Portrait.mdx')
                icon=re.fullmatch(r'ReplaceableTextures\\CommandButtons\\BTN([^\\]+)\.blp',name,re.I)
                if icon:names.add('ReplaceableTextures\\CommandButtonsDisabled\\DISBTN'+icon.group(1)+'.blp')
                if len(names)>10000:raise DefinitionError('地图资源路径数量超出处理范围，已停止处理。')
    return names


def _identify_archive_names(archive,journal):
    """Recover stripped names from actual map references before rehashing."""
    initial=archive.members();unknown=[m for m in initial if unknown_member_name(m.name)]
    if not unknown:return
    hints=set();scanned=0;seen=set();probed=set();resolved=set();rounds=0
    for rounds in range(1,9):
        current=archive.members()
        if not any(unknown_member_name(m.name) for m in current):break
        candidates=[m for m in current if (m.block_index,m.locale) not in seen and
            not m.name.lower().endswith(('.blp','.tga','.dds','.wav','.mp3','.ogg','.flac','.w3x','.w3m'))]
        # Learn paths from named scripts/objects before opening unnamed encrypted
        # models. Small encrypted files require their real basename for the key.
        named=[m for m in candidates if not unknown_member_name(m.name)]
        candidates=named or [m for m in candidates if not m.flags&0x10000 and m.size<=32*1024*1024]
        if not candidates:break
        for member in candidates:
            journal.check()
            if member.size>32*1024*1024 or scanned+member.size>128*1024*1024:
                raise DefinitionError('地图资源文件名识别的数据量超出范围，已停止处理。')
            raw=archive.read(member);scanned+=len(raw);seen.add((member.block_index,member.locale))
            hints.update(_reference_names(raw))
            if len(hints)>10000:raise DefinitionError('地图资源路径数量超出处理范围，已停止处理。')
        resolved.update(archive.identify_names(sorted(hints-probed)));probed.update(hints)
    remaining=[m.name for m in archive.members() if unknown_member_name(m.name)]
    journal.event('archive_reference_names_identified',archive=archive.path.name,
        unknown_before=len(unknown),unknown_after=len(remaining),candidate_count=len(hints),
        names_matched=sorted(resolved),scan_bytes=scanned,rounds=rounds,remaining_examples=remaining[:16],
        strategy='exact_hash_matches_from_existing_map_strings')


def _neutral(members,name):
    matches=[member for (key,_),member in members.items() if key==name.casefold()]
    if len(matches)>1 or matches and matches[0].locale!=0:
        raise DefinitionError('地图数据有多个语言副本，请单独处理：'+name)
    return matches[0] if matches else None


def _custom_ids(archive,prefix,journal=None):
    result=set()
    for suffix,extended in OBJECT_FILES:
        for stem in (prefix,prefix+'Skin'):
            raw=archive.read(stem+'.'+suffix,optional=True)
            if raw is not None:
                name=stem+'.'+suffix;details={}
                if journal:journal.event('custom_object_begin',name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                try:result.update(object_ids(raw,extended=extended,diagnostics=details))
                except DefinitionError as exc:
                    if journal:journal.event('custom_object_failed',name=name,**details)
                    raise DefinitionError('读取 '+name+' 失败：'+str(exc)) from exc
                if journal:journal.event('custom_object_verified',name=name,**details)
    return result


def _critical_check(name,raw,reference,manifest):
    if not name.endswith('.slk'):return {}
    current,wanted=parse_slk(raw),parse_slk(reference)
    ids=(manifest['critical_abilities'] if name=='AbilityData.slk' else
         manifest['critical_items'] if name=='ItemData.slk' else ())
    evidence={}
    for key in ids:
        if key not in current.rows or key not in wanted.rows:
            raise DefinitionError('关键背包定义校验失败：'+key)
        expected=wanted.rows[key];actual=current.rows[key]
        for field,value in expected.items():
            if (field in ('code','levels','abilList') or field.startswith(('Data','BuffID','EfctID'))):
                if _value(value) in ('','-','_'):continue
                if _value(actual.get(field,'K""'))!=_value(value):
                    raise DefinitionError('地图已修改同编号的背包或天赋定义，请单独处理：'+key+' / '+field)
        evidence[key]={field:_value(value) for field,value in actual.items()
                       if field in ('code','version','levels','abilList','equipment')
                       or field.startswith(('Data','BuffID','EfctID')) and _value(value) not in ('','-','_','0')}
    return evidence


def _plan(archive,members,mode,inherited,custom,manifest,files,journal):
    critical=set(manifest['critical_abilities'])|set(manifest['critical_items'])
    conflicts=critical&custom
    if conflicts:raise DefinitionError('地图自定义对象占用了背包或天赋编号：'+', '.join(sorted(conflicts)))
    plan={};details=[]
    for name,required in manifest['required'].items():
        journal.check();path='Units\\'+name;member=_neutral(members,path)
        raw=archive.read(member) if member else inherited.get(path.casefold())
        origin='map' if member else 'campaign' if raw is not None else mode
        if raw is None:raw=files['baseline/'+mode+'/'+name]
        reference=files['additions/'+name]
        merger=merge_slk if name.endswith('.slk') else merge_profile
        result,added=merger(raw,reference)
        availability={}
        if name.endswith('.slk'):
            result,version_changes=make_extension_versions_compatible(result,reference,required)
            compatible_rows=parse_slk(result).rows
            availability=dict(policy='pack_generation_2_to_universal_0',
                reason='legacy object-version gate filters generation 2 even when SLK rows exist',
                version_changes=version_changes,
                versions={key:_value(compatible_rows[key].get('version','K-1'))
                          for key in required} if name in ('AbilityData.slk','ItemData.slk') else {})
            journal.event('object_availability_verified',path=path,**availability)
        parsed=(parse_slk(result).rows if name.endswith('.slk') else parse_profile(result))
        layout={}
        if name.endswith('.slk'):
            old_table=parse_slk(raw);checked=validate_game_slk(result)
            layout=dict(original_max_column=old_table.max_x,output_max_column=checked.max_x,
                named_fields=len(checked.columns),game_column_limit=202,
                ignored_unnamed_cells=sum(x not in old_table.columns for row in old_table.opaque.values() for x in row))
            journal.event('table_layout_verified',path=path,**layout)
        if not set(required)<=set(parsed):raise DefinitionError('补齐后的定义依赖仍有缺项：'+name)
        if name.endswith('.slk') and set(added)&custom:
            raise DefinitionError('地图自定义对象与新增定义编号冲突：'+', '.join(sorted(set(added)&custom)))
        critical_definitions=_critical_check(name,result,reference,manifest)
        # Even when the baseline contains some rows, a custom-mode map must
        # carry the explicit table so the game does not choose the old overlay.
        if member is None or result!=raw:plan[path]=(result,member)
        details.append(dict(path=path,origin=origin,added=list(added),bytes=len(result),
                            sha256=hashlib.sha256(result).hexdigest(),write=path in plan,
                            critical_definitions=critical_definitions,layout=layout,availability=availability))
    return plan,details


def _fingerprints(archive,members,journal):
    result={}
    for index,(key,member) in enumerate(members.items(),1):
        journal.check()
        if index==1 or index%32==0:journal.event('scan_archive',path=member.name,index=index,total=len(members))
        if key[0] in META:continue
        result[key]=(hashlib.sha256(archive.read(member)).hexdigest(),member.flags&STORAGE_FLAGS)
    return result


def _verify(path,before,expected,journal):
    journal.event('archive_verify',path=path.name)
    with Archive(path) as archive:
        hints=[]
        for key in set(before)|set(expected):
            if unknown_member_name(key[0]):continue
            # Existing archives may contain noncanonical resource names. They
            # remain accessible by their Member and are never exported as paths.
            # Such names need no optional filename hint if already in listfile.
            try:hints.append(canonical_name(key[0]))
            except MpqError:continue
        archive.identify_names(hints)
        members=_members(archive,journal)
        for index,(key,(digest,flags)) in enumerate(before.items(),1):
            journal.check();member=members.get(key)
            if index==1 or index%32==0:journal.event('verify_member',path=key[0],index=index,total=len(before))
            if member is None or member.flags&STORAGE_FLAGS!=flags:
                raise DefinitionError('原有文件目录或压缩方式校验失败：'+key[0])
            if hashlib.sha256(archive.read(member)).hexdigest()!=expected.get(key,digest):
                raise DefinitionError('原有文件内容或处理结果校验失败：'+key[0])
        for key,digest in expected.items():
            member=members.get(key)
            if member is None or hashlib.sha256(archive.read(member)).hexdigest()!=digest:
                raise DefinitionError('新增定义重新读取校验失败：'+key[0])
        if set(members)-set(before)-set(expected)-{key for key in members if key[0] in META}:
            raise DefinitionError('输出归档包含未预期的新增文件。')


def _patch_map(path,inherited,parent_custom,manifest,files,journal):
    with Archive(path) as archive:
        archive.identify_names('Units\\'+name for name in manifest['required'])
        _identify_archive_names(archive,journal)
        members=_members(archive,journal);metadata=map_data_mode(archive.read('war3map.w3i'))
        script_checks=[]
        if metadata['script_language']==0:
            for script in ('war3map.j','scripts\\war3map.j'):
                payload=archive.read(script,optional=True)
                if payload is None:continue
                try:validation=check_function_order(payload)
                except DefinitionError as exc:
                    journal.event('script_validation_failed',path=script,**getattr(exc,'script_diagnostics',{}));raise
                journal.event('script_function_order_verified',path=script,**validation)
                script_checks.append(dict(path=script,sha256=hashlib.sha256(payload).hexdigest(),**validation))
        else:journal.event('script_validation_skipped',language=metadata['script_language'],reason='JASS order check does not validate Lua')
        journal.event('archive_names_identified',archive=path.name,member_count=len(members),
            known_warcraft_names=list(archive.identified_names))
        custom=parent_custom|_custom_ids(archive,'war3map',journal)
        before=_fingerprints(archive,members,journal)
        plan,details=_plan(archive,members,metadata['mode'],inherited,custom,manifest,files,journal)
    with Archive(path,writable=True) as archive:
        archive.identify_names('Units\\'+name for name in manifest['required'])
        _identify_archive_names(archive,journal)
        if plan:
            archive.reserve(sum(member is None for raw,member in plan.values()),
                progress=lambda stage,data:journal.event(stage,**data))
            for name,(raw,member) in plan.items():
                journal.event('write_table',map=path.name,path=name,bytes=len(raw),original_flags=member.flags if member else None)
                archive.write(name,raw,original=member)
            archive.flush()
        compaction=archive.compact(progress=lambda stage,data:journal.event(stage,**data))
    expected={(name.casefold(),0):hashlib.sha256(raw).hexdigest() for name,(raw,member) in plan.items()}
    _verify(path,before,expected,journal)
    return dict(metadata=metadata,tables=details,script_checks=script_checks,
                changed=bool(plan) or compaction['performed'],archive_compaction=compaction,
                added_entries=sum(len(row['added']) for row in details))


def prepare_extension_definitions(source,output_folder,*,progress=None,cancel=None):
    try: source=Path(str(source).strip().strip('"')).expanduser().resolve(strict=True)
    except OSError as exc: raise DefinitionError('输入文件没有找到或读取失败，请检查完整路径。') from exc
    if source.suffix.casefold() not in ('.w3n','.w3x','.w3m') or not source.is_file():
        raise DefinitionError('请选择 w3n 战役或 w3x 地图文件。')
    if source.stat().st_size>8*1024**3:raise DefinitionError('这份战役或地图过大，请单独处理。')
    manifest,files=definition_pack()
    folder=Path(output_folder).expanduser().resolve()
    folder.mkdir(parents=True,exist_ok=True)
    run_folder=folder/(source.stem[:70]+'-3.0背包定义-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    run_folder.mkdir(exist_ok=False)
    journal=Journal(run_folder/'处理日志.jsonl',progress,cancel)
    pending=run_folder/('未完成.tmp')
    current_chapter = None
    try:
        initial_stat=(source.stat().st_size,source.stat().st_mtime_ns)
        journal.event('source_hash_begin',source=str(source),log_path=str(journal.path))
        source_hash=file_hash(source)
        journal.event('start',source=str(source),source_sha256=source_hash,pack_id=manifest['pack_id'],
                      pack_sha256=PACK_SHA256,source_game=manifest['source_game'],original_edited=False,
                      processing_revision=PROCESSING_REVISION)
        with tempfile.TemporaryDirectory(prefix='war3-definitions-') as temporary:
            work=Path(temporary);staged=work/('campaign'+source.suffix)
            journal.event('copy_begin',path=source.name)
            shutil.copyfile(source,staged)
            if file_hash(staged)!=source_hash:raise DefinitionError('输入文件复制校验失败，请重新选择文件。')
            journal.event('source_copied',path=source.name)
            reports=[]
            if source.suffix.casefold()=='.w3n':
                with Archive(staged) as archive:
                    members=_members(archive,journal);before=_fingerprints(archive,members,journal)
                    referenced=campaign_maps(archive.read('war3campaign.w3f'))
                    chapters=[m for m in members.values() if m.name.casefold().endswith(('.w3x','.w3m'))]
                    if not chapters or len(chapters)>1000:raise DefinitionError('战役章节列表为空或数量异常。')
                    names={m.name.casefold() for m in chapters}
                    if not {canonical_name(name).casefold() for name in referenced}<=names:
                        raise DefinitionError('战役目录缺少被引用的章节，已停止处理。')
                    inherited={}
                    for name in manifest['required']:
                        path='Units\\'+name;member=_neutral(members,path)
                        if member:inherited[path.casefold()]=archive.read(member)
                    custom=_custom_ids(archive,'war3campaign',journal)
                    for index,member in enumerate(chapters):
                        canonical_name(member.name)
                        chapter=work/('chapter-'+str(index)+'.w3x')
                        chapter.write_bytes(archive.read(member))
                        reports.append(dict(name=member.name,stage_path=str(chapter),original_flags=member.flags))
                changes=[];expected={}
                for index,report in enumerate(reports):
                    current_chapter=report['name']
                    journal.event('chapter_begin',index=index+1,total=len(reports),name=report['name'])
                    chapter=Path(report.pop('stage_path'))
                    report.update(_patch_map(chapter,inherited,custom,manifest,files,journal))
                    journal.event('chapter_verified',**report)
                    if report['changed']:
                        member=members[(report['name'].casefold(),0)]
                        changes.append((member,chapter));expected[(member.name.casefold(),0)]=file_hash(chapter)
                with Archive(staged,writable=True) as archive:
                    if changes:
                        for member,chapter in changes:
                            journal.event('replace_chapter',name=member.name,original_flags=member.flags)
                            archive.write(member.name,chapter.read_bytes(),original=member)
                        archive.flush()
                    archive.compact(progress=lambda stage,data:journal.event(stage,**data))
                _verify(staged,before,expected,journal)
            else:
                current_chapter=source.name
                journal.event('chapter_begin',index=1,total=1,name=source.name)
                reports=[dict(name=source.name,**_patch_map(staged,{},set(),manifest,files,journal))]
                journal.event('chapter_verified',**reports[0])
            journal.check()
            if (source.stat().st_size,source.stat().st_mtime_ns)!=initial_stat or file_hash(source)!=source_hash:
                raise DefinitionError('处理期间输入文件发生变化，已停止输出，请重新选择文件。')
            journal.event('output_verify',path=source.name)
            digest=file_hash(staged);shutil.copyfile(staged,pending)
            if file_hash(pending)!=digest:raise DefinitionError('输出文件复制校验失败。')
            output=run_folder/(source.stem+'_3.0背包定义'+source.suffix)
            report_path=run_folder/'处理报告.json'
            report=dict(schema=1,source=str(source),source_sha256=source_hash,output=str(output),
                        output_sha256=digest,pack_id=manifest['pack_id'],processing_revision=PROCESSING_REVISION,chapters=reports,
                        verification=dict(all_original_members_preserved=True,storage_flags_preserved=True,
                                          source_unchanged=True,added_definitions_reextracted=True,
                                          gameplay_tested=False,old_saved_games_updated=False,
                                          runtime_validation_required=True))
            report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            journal.event('verified',report_path=str(report_path),output=str(output),output_sha256=digest)
            os.fsync(journal.stream.fileno());journal.check();journal.close()
            os.replace(pending,output)
            return DefinitionResult(str(source),str(output),str(report_path),str(journal.path),len(reports),
                                    sum(row['changed'] for row in reports),sum(row['added_entries'] for row in reports),
                                    source_hash,digest)
    except Exception as exc:
        pending.unlink(missing_ok=True)
        # Keep the diagnostic directory even when no campaign/map is published.
        try:
            journal.stream.write(json.dumps(dict(stage='failed',exception=repr(exc),traceback=traceback.format_exc(),
                                                 source=str(source),chapter=current_chapter,
                                                 archive_details=getattr(exc,'mpq_details',{}),
                                                 script_details=getattr(exc,'script_diagnostics',{}),output_published=False),ensure_ascii=False)+'\n')
            journal.stream.flush()
        except (OSError,ValueError):pass
        if isinstance(exc,DefinitionError) and current_chapter:
            error=DefinitionError(f'处理章节“{current_chapter}”时：'+str(exc));error.__cause__=exc;exc=error
        elif not isinstance(exc,DefinitionError):
            error=DefinitionError((f'处理章节“{current_chapter}”时：' if current_chapter else '')+str(exc)
                if isinstance(exc,MpqError) else '处理战役或地图时出错，原文件已保留。详细原因已记录在处理日志中。')
            error.__cause__=exc;exc=error
        exc.diagnostic_log_path=str(journal.path)
        raise exc
    finally:
        try:journal.close()
        except OSError:pass
