// Public surface of the design system. Pages import from 'src/ds' only.
export { DsProvider } from './DsProvider'
export { useWindowFocused } from './hooks'
export * from './tokens'
export { cx } from './util'

export { Icon, type IconTone } from './icons/Icon'
export { ICON_ATTRIBUTION, ICON_GROUPS, ICON_SOURCES, type IconName } from './icons/generated'

export { Button, type ButtonProps } from './primitives/Button'
export { Checkbox, PillGroup, Select, TextArea, TextField, type PillOption, type SelectProps, type TextFieldProps } from './primitives/Fields'
export { Frame, GroupHeader, Keycap, PlayerSwatch, RawcodePlate } from './primitives/Bits'
export { ProgressBar, StatBar, XpBar, lifeGradient } from './primitives/Bars'
export { Tooltip, TooltipCard } from './primitives/Tooltip'
export { Dialog, DialogClose } from './primitives/Dialog'

export { EditableNumber, EditableText, RollingNumber, type EditableNumberProps, type EditableTextProps } from './motion/Numbers'
export { announce, bounty, type BountyOptions, type BountyTone } from './motion/Layers'
export { Frost, SelectionRing, type Relation, type SelectionState } from './motion/Effects'
export { CommandCard, GRID_KEYS, type CommandSpec, type GridKey } from './motion/CommandCard'
export { HoldToConfirm } from './motion/HoldToConfirm'
export { FogReveal } from './motion/FogReveal'
