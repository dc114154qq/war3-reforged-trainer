import { lazy, type ComponentType, type LazyExoticComponent } from 'react'
import type { PageId } from '../routes'

/**
 * Every page of the trainer, each loaded as its own chunk. The record type makes a missing
 * page a compile error; --ui-check opens each one and requires it to have controls.
 */
export const PAGES: Record<PageId, LazyExoticComponent<ComponentType>> = {
  resources: lazy(() => import('./battle/ResourcesPage')),
  unit: lazy(() => import('./battle/UnitPage')),
  batch: lazy(() => import('./battle/BatchPage')),
  locks: lazy(() => import('./battle/LocksPage')),
  unit_fields: lazy(() => import('./fields/UnitFieldsPage')),
  ability_fields: lazy(() => import('./fields/AbilityFieldsPage')),
  item_fields: lazy(() => import('./fields/ItemFieldsPage')),
  extensions: lazy(() => import('./fields/ExtensionsPage')),
  elephant: lazy(() => import('./elephant/ElephantPage')),
  hotkeys: lazy(() => import('./elephant/HotkeysPage')),
  catalogs: lazy(() => import('./codex/CatalogPage')),
  upgrade_catalog: lazy(() => import('./codex/UpgradeCatalogPage')),
  map_catalog: lazy(() => import('./codex/MapCatalogPage')),
  equipment3: lazy(() => import('./codex/Equipment3Page')),
  hero_skills: lazy(() => import('./codex/HeroSkillsPage')),
  map_scripts: lazy(() => import('./huolong/MapScriptsPage')),
  archive: lazy(() => import('./archive/ArchivePage')),
}

/** Rendered by the stage as data-ready; --ui-check fails on any page without it. */
export const isReady = (page: PageId) => page in PAGES
