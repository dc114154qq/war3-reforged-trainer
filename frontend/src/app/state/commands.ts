import { useEffect, useRef } from 'react'
import { create } from 'zustand'
import type { CommandSpec } from '../../ds'

/**
 * The console's command card follows the page, as the in-game card follows the selected
 * unit. A page publishes its commands with useCommandCard(); keys it leaves free keep the
 * shell's defaults (Q reads all selected units).
 */
export const useCommands = create<{ page: CommandSpec[]; owner: symbol | null }>(() => ({ page: [], owner: null }))

export function useCommandCard(commands: CommandSpec[]) {
  const owner = useRef(Symbol('page-commands'))
  // Commands carry closures and pending flags, so they are republished on every render.
  useEffect(() => { useCommands.setState({ page: commands, owner: owner.current }) })
  // Exit animation can unmount the previous page after the next has published.
  // Only the page that still owns the card may clear it.
  useEffect(() => () => {
    if (useCommands.getState().owner === owner.current) useCommands.setState({ page: [], owner: null })
  }, [])
}
