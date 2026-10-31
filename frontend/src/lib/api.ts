export interface MapCatalogChange {field:string;label:string;labelEn?:string;level:number;index:number;value:unknown;rawValue:unknown;baseValue:unknown;baseKnown:boolean;file:string;storage:string;}
export interface MapCatalogRow {heroNames?:string[];isHero?:boolean;id:string;kind:string;rawcode:string;base:string;name:string;description:string;scope:string;changeType:string;changeCount:number;files:string[];changes?:MapCatalogChange[];}
export interface CatalogDiagnostic {scope:string;file:string;message:string;impact?:string;severity?:string;stringId?:string;byteOffset?:number;usedBy?:string[];}
export interface MapCatalogProgress {diagnostics?:CatalogDiagnostic[];jobId:string;status:string;elapsed:number;stage?:string;source?:string;scope?:string;file?:string;index?:number;total?:number;rowCount?:number;counts?:Record<string,number>;scopes?:string[];warnings?:{scope:string;file:string;message:string}[];error?:string;notice?:string;}

import type {
  SystemStatus,
  ResourceSnapshot,
  GoldMineData,
  SelectedUnitData,
  CandidateUnit,
  LockItem,
  AbilityFieldsData,
  ItemFieldsData,
  ExtensionsSnapshot,
  ArtifactPlanData,
  HotkeyItem,
  CatalogSearchData,
  Equipment3SearchData,
  HeroSkillsSearchData,
  ArchiveRow,
  RpgCodeRow,
} from './types';

declare global {
  interface Window {
    pywebview?: {
      api: Record<string, (...args: any[]) => Promise<any>>;
    };
  }
}

// Helper to safely call the backend API
async function callApi<T>(method: string, ...args: any[]): Promise<T> {
  if (!window.pywebview?.api) await new Promise<void>((resolve,reject) => {
    const ready=()=>{clearTimeout(timer);resolve();};
    const timer=setTimeout(()=>{window.removeEventListener('pywebviewready',ready);reject(new Error('桌面通信尚未就绪，请重新打开修改器。'));},10000);
    window.addEventListener('pywebviewready',ready,{once:true});
    if(window.pywebview?.api)ready();
  }).catch(err=>{window.dispatchEvent(new CustomEvent('war3-error',{detail:{message:err.message}}));throw err;});
  if (typeof window !== 'undefined' && window.pywebview?.api?.[method]) {
    try {
      const result = await window.pywebview.api[method](...args);
      if(result?.parameters || result?.changedParameters)window.dispatchEvent(new CustomEvent('war3-elephant-parameters',{detail:result.parameters || result.changedParameters}));
      if(method==='set_hotkey_parameter' && result?.success)window.dispatchEvent(new CustomEvent('war3-elephant-parameters-changed'));
      if (result?.success === false && !result.cancelled) {
        const detail={message:result.error || '操作未完成',logPath:result.logPath,id:result.notificationId};
        window.dispatchEvent(new CustomEvent('war3-error', {detail}));
        if(!('reports' in result))throw Object.assign(new Error(detail.message),{reported:true});
      }
      return result as T;
    } catch (err) {
      console.error(`pywebview.api.${method} failed:`, err);
      if(!(err as {reported?:boolean})?.reported)window.dispatchEvent(new CustomEvent('war3-error', {detail: {message:err instanceof Error ? err.message : String(err)}}));
      throw err;
    }
  }

  throw new Error('桌面通信尚未就绪，请在修改器桌面窗口内重试');
}

export const api = {
  getMapScriptOptions: () => callApi<{success:boolean;options:MapScriptOptions;features:Record<string,string>}>('get_map_script_options'),
  saveMapScriptOptions: (options:MapScriptOptions) => callApi<{success:boolean;options:MapScriptOptions}>('save_map_script_options',options),
  startMapScripts: (paths:string[],folder:string,options:MapScriptOptions,combined=false) => callApi<{success:boolean;jobId:string}>('start_map_scripts',paths,folder,options,combined),
  getMapScriptProgress: (id='') => callApi<MapScriptProgress>('get_map_script_progress',id),
  cancelMapScripts: (id='') => callApi<{success:boolean}>('cancel_map_scripts',id),
  startMapCatalog: (path:string) => callApi<{success:boolean;jobId:string}>('start_map_catalog',path),
  getMapCatalogProgress: (id='') => callApi<MapCatalogProgress>('get_map_catalog_progress',id),
  cancelMapCatalog: (id='') => callApi<{success:boolean}>('cancel_map_catalog',id),
  searchMapCatalog: (id:string,kind='',query='',scope='',changeType='',offset=0) => callApi<{success:boolean;rows:MapCatalogRow[];matchCount:number;totalCount:number}>('search_map_catalog',id,kind,query,scope,changeType,offset),
  getMapCatalogEntry: (id:string,row:string) => callApi<MapCatalogRow>('get_map_catalog_entry',id,row),
  exportMapCatalog: (id:string,format='csv',kind='',query='',scope='',changeType='') => callApi<{success:boolean;cancelled?:boolean;path?:string;count?:number}>('export_map_catalog',id,format,kind,query,scope,changeType),
  goldMines: (scope: 'selected' | 'world', amount?: string) =>
    callApi<{success: boolean; data?: GoldMineData; error?: string; reports?: GoldMineData['rows']}>('gold_mines', scope, amount ?? null),
  // 1. System
  getSystemStatus: () => callApi<SystemStatus>('get_system_status'),
  getUiNotifications: () => callApi<UiNotice[]>('get_ui_notifications'),
  connectProcess: (pid?: number | null) => callApi<{ success: boolean; status: SystemStatus; error?: string }>('connect_process', pid),
  cancelDiscovery: () => callApi<{ success: boolean; error?: string }>('cancel_discovery'),
  setHotkeysEnabled: (enabled: boolean) => callApi<{ success: boolean; enabled: boolean; status: string }>('set_hotkeys_enabled', enabled),
  setUiLanguage: (lang: 'zh' | 'en') => callApi<{ success: boolean; language: string; translations: Record<string, string> }>('set_ui_language', lang),

  // 2. Resources
  selectResourceGroup: (iid: string) => callApi<ResourceSnapshot>('select_resource_group', iid),
  getSelectedUnitSnapshot: () => callApi<SelectedUnitData>('get_selected_unit_snapshot'),
  readAllSelectedUnits: () => callApi<{unit:SelectedUnitData;candidates:CandidateUnit[]}>('read_all_selected_units'),
  getUnitCandidatesSnapshot: () => callApi<CandidateUnit[]>('get_unit_candidates_snapshot'),
  getResourceSnapshot: () => callApi<ResourceSnapshot>('get_resource_snapshot'),
  refreshResources: () => callApi<{ success: boolean; data: ResourceSnapshot; error?: string }>('refresh_resources'),
  setResource: (kind: string, value: string) => callApi<{ success: boolean; data: ResourceSnapshot; error?: string }>('set_resource', kind, value),
  addResource: (kind: string, delta?: string) => callApi<{ success: boolean; data: ResourceSnapshot; error?: string }>('add_resource', kind, delta),
  addResourceLock: (kind: string) => callApi<{ success: boolean; locks: LockItem[] }>('add_resource_lock', kind),

  // 3. Unit
  readSelectedUnit: () => callApi<SelectedUnitData>('read_selected_unit'),
  readUnitFields: () => callApi<import('./types').NativeUnitFieldsData>('read_unit_fields'),
  writeUnitFieldValue: (key: string, value: string) =>
    callApi<{ success: boolean; key: string; value: import('./types').NativeUnitField['value'] }>('write_unit_field_value', key, value),
  writeSelectedUnit: (targets: Record<string, string>) => callApi<{ success: boolean; data?: SelectedUnitData; error?: string }>('write_selected_unit', targets),
  writeUnitField: (rowIid: string, value: string) => callApi<{ success: boolean; data?: SelectedUnitData; error?: string }>('write_unit_field', rowIid, value),
  addUnitFieldLock: (rowIid: string, value: string) => callApi<{ success: boolean; locks?: LockItem[]; error?: string }>('add_unit_field_lock', rowIid, value),
  refreshUnitCandidates: () => callApi<CandidateUnit[]>('refresh_unit_candidates'),
  readSelectionCandidate: (candidateIid: string) => callApi<{ success: boolean; unit?: SelectedUnitData; error?: string }>('read_selection_candidate', candidateIid),
  readNativeSelection: () => callApi<{ success: boolean; unit?: SelectedUnitData; error?: string }>('read_native_selection'),

  // 4. Locks
  getLocks: () => callApi<LockItem[]>('get_locks'),
  applyLocksOnce: () => callApi<{ success: boolean; message?: string; error?: string }>('apply_locks_once'),
  removeLock: (lockIid: string) => callApi<{ success: boolean; locks: LockItem[]; error?: string }>('remove_lock', lockIid),

  // 5. Ability Fields
  readAbilityFields: (rawcode: string, level: string, filterText?: string, showZero?: boolean, showUnsupported?: boolean) =>
    callApi<AbilityFieldsData>('read_ability_fields', rawcode, level, filterText ?? '', showZero ?? true, showUnsupported ?? true),
  writeAbilityField: (rowIid: string, newValue: string) =>
    callApi<{ success: boolean; data?: AbilityFieldsData; error?: string }>('write_ability_field', rowIid, newValue),

  // 6. Item Fields
  readItemFields: (slot: string, filterText?: string, showZero?: boolean, showUnsupported?: boolean) =>
    callApi<ItemFieldsData>('read_item_fields', slot, filterText ?? '', showZero ?? true, showUnsupported ?? true),
  readItemEffectFields: (area: string, slot: string, level: string) =>
    callApi<ItemFieldsData>('read_item_effect_fields', area, slot, level),
  writeItemEffectField: (rowIid: string, newValue: string) =>
    callApi<{ success: boolean; data?: ItemFieldsData; error?: string }>('write_item_effect_field', rowIid, newValue),
  writeItemField: (rowIid: string, newValue: string) =>
    callApi<{ success: boolean; data?: ItemFieldsData; error?: string }>('write_item_field', rowIid, newValue),

  // 7. Extensions
  refreshExtensionStatus: () => callApi<ExtensionsSnapshot>('refresh_extension_status'),
  extensionBagAction: (action: string, params?: Record<string, any>) =>
    callApi<{ success: boolean; data?: ExtensionsSnapshot; message?: string; error?: string }>('extension_bag_action', action, params),
  extensionEquipmentAction: (action: string, params?: Record<string, any>) =>
    callApi<{ success: boolean; data?: ExtensionsSnapshot; message?: string; error?: string }>('extension_equipment_action', action, params),
  extensionTalentAction: (action: string, params?: Record<string, any>) =>
    callApi<{ success: boolean; data?: ExtensionsSnapshot; message?: string; error?: string }>('extension_talent_action', action, params),
  prepareBackpackDefinitions: (mapPath: string, outputFolder = '') =>
    callApi<{ success: boolean; destination?: string; report?: { report_path: string; log_path: string }; message?: string; error?: string; logPath?: string }>('prepare_backpack_definitions', mapPath, outputFolder),

  // 8. Elephant Actions
  getElephantParameters: () => callApi<Record<string,string>>('get_elephant_parameters'),
  setElephantParameter: (key:string,value:string) => callApi<{success:boolean;changedParameters:Record<string,string>}>('set_elephant_parameter',key,value),
  startBackpackDefinitions: (path:string,folder='') => callApi<{success:boolean;jobId:string}>('start_backpack_definitions',path,folder),
  startBackpackDefinitionsBatch: (paths:string[],folder='') => callApi<{success:boolean;jobId:string}>('start_backpack_definitions_batch',paths,folder),
  getBackpackDefinitionProgress: (id='') => callApi<DefinitionProgress>('get_backpack_definition_progress',id),
  cancelBackpackDefinitions: (id='') => callApi<{success:boolean}>('cancel_backpack_definitions',id),
  chooseDefinitionFile: () => callApi<{success:boolean;path:string;cancelled:boolean}>('choose_definition_file'),
  chooseDefinitionFiles: () => callApi<{success:boolean;paths:string[];cancelled:boolean}>('choose_definition_files'),
  chooseDefinitionFolder: () => callApi<{success:boolean;path:string;cancelled:boolean}>('choose_definition_folder'),
  prewarmElephant: () => callApi<{ success: boolean; message?: string; error?: string }>('prewarm_elephant'),
  executeElephantAction: (actionName: string, params?: Record<string, any>) =>
    callApi<{ success: boolean; action?: string; error?: string }>('execute_elephant_action', actionName, params),

  // 9. Artifact Plan
  getArtifactPlan: () => callApi<ArtifactPlanData>('get_artifact_plan'),
  saveArtifactPlan: (codes: string[]) => callApi<{ success: boolean; plan?: ArtifactPlanData; error?: string }>('save_artifact_plan', codes),
  restoreDefaultArtifactPlan: () => callApi<{ success: boolean; plan?: ArtifactPlanData; error?: string }>('restore_default_artifact_plan'),
  applyArtifactPlan: (codes?: string[]) => callApi<{ success: boolean; message?: string; error?: string }>('apply_artifact_plan', codes),

  // 10. Hotkeys
  getAllHotkeys: () => callApi<HotkeyItem[]>('get_all_hotkeys'),
  setHotkeyCheck: (name: string, enabled: boolean) => callApi<{ success: boolean; name?: string; enabled?: boolean; error?: string }>('set_hotkey_check', name, enabled),
  setAllHotkeysChecks: (enabled: boolean) => callApi<{ success: boolean; enabled: boolean; hotkeys: HotkeyItem[] }>('set_all_hotkeys_checks', enabled),
  setHotkeyParameter: (paramKey: string, value: string) => callApi<{ success: boolean; paramKey?: string; value?: string; error?: string }>('set_hotkey_parameter', paramKey, value),
  triggerHotkey: (name: string) => callApi<{ success: boolean; name?: string; message?: string; error?: string }>('trigger_hotkey', name),

  // 11-14. Catalogs
  searchIdCatalog: (kind: 'item' | 'ability' | 'unit' | 'upgrade', query?: string) => callApi<CatalogSearchData>('search_id_catalog', kind, query ?? ''),
  search3Equipment: (query?: string) => callApi<Equipment3SearchData>('search_3_equipment', query ?? ''),
  search3HeroSkills: (hero?: string, query?: string) => callApi<HeroSkillsSearchData>('search_3_hero_skills', hero ?? '', query ?? ''),

  // 15. Batch & Archive
  batchReadUnits: () => callApi<{ success: boolean; units?: any[]; fields?: any[]; error?: string }>('batch_read_units'),
  batchWriteUnits: (unitInstances: string[], targetFields: Record<string, string>) =>
    callApi<{ success: boolean; message?: string; reports?: any[]; error?: string }>('batch_write_units', unitInstances, targetFields),
  scanArchiveDirectory: (dirPath?: string) => callApi<{ success: boolean; directory?: string; files?: any[]; error?: string }>('scan_archive_directory', dirPath ?? ''),
  readArchiveFile: (filePath: string) => callApi<{ success: boolean; filePath?: string; rows?: ArchiveRow[]; error?: string }>('read_archive_file', filePath),
  readLiveHeroes: () => callApi<{ success: boolean; rows?: ArchiveRow[]; error?: string }>('read_live_heroes'),
  scanRpgCodesMemory: (prefix?: string) => callApi<{ success: boolean; rows?: RpgCodeRow[]; error?: string }>('scan_rpg_codes_memory', prefix ?? '-load'),
  parseRpgCodesText: (text: string, prefix?: string) => callApi<{ success: boolean; rows?: RpgCodeRow[]; error?: string }>('parse_rpg_codes_text', text, prefix ?? '-load'),
};

export interface UiNotice { details?:CatalogDiagnostic[];context?:string;id?:number;title?:string;message:string;logPath?:string;kind?:string;unit?:SelectedUnitData;candidates?:CandidateUnit[];parameters?:Record<string,string>; }
export interface DefinitionFileResult {source:string;status:string;destination:string;message:string;error:string;logPath:string;reportPath:string;}
export interface DefinitionResult {success?:boolean;batch?:boolean;cancelled?:boolean;files?:DefinitionFileResult[];destination?:string;report?:{report_path:string;log_path:string};message?:string;error?:string;logPath?:string;}
export interface DefinitionProgress {jobId:string;status:string;stage?:string;chapter?:string;index?:number;total?:number;completed?:number;currentFile?:string;elapsed:number;result?:DefinitionResult;error?:string;logPath?:string;batchMode?:boolean;outputFolder?:string;fileTotal?:number;fileIndex?:number;fileCompleted?:number;fileSucceeded?:number;fileFailed?:number;fileSkipped?:number;files?:DefinitionFileResult[];}
export interface MapScriptOptions {prefix:string;features:string[];artifact_codes:string[];resource_amount:number;}
export interface MapScriptProgress extends DefinitionProgress {files?:(DefinitionFileResult & {usagePath?:string})[];failures?:{source:string;reason:string;logPath:string}[];}
