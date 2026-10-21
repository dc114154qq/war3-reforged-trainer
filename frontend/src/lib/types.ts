export interface SystemStatus {
  appVersion: string;
  edition: string;
  connected: boolean;
  pid: number | null;
  gameVersion: string | null;
  adapterProfile: string | null;
  bridgeProfile: number;
  hotkeysEnabled: boolean;
  statusMessage: string;
  language: 'zh' | 'en';
}

export interface ResourceGroup {
  _iid: string;
  group: string;
  gold: number | string;
  lumber: number | string;
  food: number | string;
  gold_address: string;
  lumber_address: string;
  source: string;
}

export interface ResourceSnapshot {
  current: {
    gold: string;
    lumber: string;
    food: string;
    foodCap: string;
  };
  targets: {
    gold: string;
    lumber: string;
    foodUsed: string;
    foodCap: string;
  };
  delta: string;
  groups: ResourceGroup[];
}

export interface UnitFieldRow {
  _iid: string;
  category: string;
  label: string;
  value: string;
  type: string;
  address: string;
  note: string;
}

export interface CandidateUnit {
  _iid: string;
  index: string;
  confidence: string;
  hp: string;
  mp: string;
  position: string;
  evidence: string;
  components: string;
  inventory: string;
  handle: string;
  owner: string;
  unit: string;
}

export interface SelectedUnitData {
  hasSelection: boolean;
  unitTypeId: string;
  identity: string | null;
  hp: {
    current: string;
    max: string;
    regen: string;
    target: string;
    regenTarget: string;
  };
  mp: {
    current: string;
    max: string;
    regen: string;
    target: string;
    regenTarget: string;
  };
  position: {
    xCurrent: string;
    yCurrent: string;
    xTarget: string;
    yTarget: string;
  };
  fields: UnitFieldRow[];
}

export interface LockItem {
  _iid: string;
  scope: string;
  label: string;
  value: string;
}

export interface AbilityFieldRow {
  _iid: string;
  field: string;
  type: string;
  scope: string;
  name: string;
  value: string;
  status: string;
}

export interface AbilityFieldsData {
  summary: string;
  detail: string;
  rows: AbilityFieldRow[];
}

export interface ItemFieldRow {
  _iid: string;
  field: string;
  type: string;
  name: string;
  value: string;
  status: string;
}

export interface ItemFieldsData {
  summary: string;
  detail: string;
  rows: ItemFieldRow[];
}

export interface BagItemRow {
  _iid: string;
  slot: string;
  rawcode: string;
  charges: string;
  handle: string;
}

export interface EquipmentItemRow {
  _iid: string;
  slot: string;
  rawcode: string;
  type: string;
  charges: string;
  handle: string;
}

export interface TalentRow {
  _iid: string;
  hero: string;
  tier: string;
  choices: string;
  selected: string;
}

export interface ExtensionsSnapshot {
  status: string;
  bag: BagItemRow[];
  equipment: EquipmentItemRow[];
  talents: TalentRow[];
  officialBackpacks: string[];
  currentBackpackChoice: string;
  loadoutName: string;
  loadoutNames?: string[];
  talentChoices?: string[];
  loadoutWarnings?: Record<string, unknown>;
}

export interface ArtifactPlanData {
  codes: string[];
  isDefault: boolean;
  defaultCodes: string[];
}

export interface HotkeyItem {
  name: string;
  label: string;
  key: string;
  enabled: boolean;
  paramKey: string | null;
  paramLabel: string | null;
  paramValue: string | null;
  isDangerous: boolean;
  category: 'general' | 'stats' | 'fullscreen' | 'combat' | 'world';
}

export interface CatalogItemRow {
  rawcode: string;
  name_zh: string;
  name_en: string;
  category: string;
}

export interface CatalogSearchData {
  kind: string;
  totalCount: number;
  matchCount: number;
  rows: CatalogItemRow[];
}

export interface Equipment3Row {
  name: string;
  code: string;
  description: string;
}

export interface Equipment3SearchData {
  totalCount: number;
  matchCount: number;
  rows: Equipment3Row[];
}

export interface HeroSkillRow {
  hero: string;
  name: string;
  code: string;
  levels: string;
  description: string;
}

export interface HeroSkillsSearchData {
  heroes: string[];
  totalCount: number;
  matchCount: number;
  rows: HeroSkillRow[];
}

export interface ArchiveRow {
  scope: string;
  key: string;
  type: string;
  value: string;
}

export interface RpgCodeRow {
  kind: string;
  code: string;
  source: string;
}
