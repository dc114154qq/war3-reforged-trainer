import { useRef, useState, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { SPRING } from '../tokens'
import { cx } from '../util'
import s from './Numbers.module.css'

const DIGITS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

/**
 * Odometer. Each digit rolls to its new value, right-most first; other characters
 * (sign, decimal point, slash) stay put. Takes the already-formatted text.
 */
export function RollingNumber({ text, className }: { text: string; className?: string }) {
  const chars = [...text]
  return (
    <span className={cx(s.roll, className)} aria-label={text} role="img">
      {chars.map((c, i) => {
        const fromRight = chars.length - i
        if (c >= '0' && c <= '9') return <Digit key={`d${fromRight}`} digit={Number(c)} order={fromRight} />
        return <span key={`c${fromRight}${c}`} className={s.glyph} aria-hidden="true">{c}</span>
      })}
    </span>
  )
}

function Digit({ digit, order }: { digit: number; order: number }) {
  return (
    <span className={s.col} aria-hidden="true">
      <motion.span
        className={s.strip}
        initial={false}
        animate={{ y: `${-digit * 10}%` }}
        transition={{ ...SPRING.digit, delay: order * 0.018 }}
      >
        {DIGITS.map(d => <span key={d}>{d}</span>)}
      </motion.span>
    </span>
  )
}

const defaultParse = (text: string) => {
  const n = Number(text.trim().replace(/[−–]/g, '-').replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

export interface EditableNumberProps {
  /** Formatted value to show. */
  text: string
  /** Accessible name, e.g. the field name. */
  label: string
  /** Called with the parsed value and the cell's rect (for bounty text). */
  onCommit(value: number, rect: DOMRect | null): void
  /** Called when the typed text is not a number. */
  onInvalid?(text: string): void
  parse?(text: string): number | null
  /** Controlled editing, for opening the editor from a hotkey. */
  editing?: boolean
  onEditingChange?(editing: boolean): void
  /** Overlays such as <Frost>, laid over the value cell. */
  children?: ReactNode
  className?: string
}

/** A number that becomes an input on click. Enter writes, Esc or blur cancels. */
export function EditableNumber({
  text, label, onCommit, onInvalid, parse = defaultParse, editing: controlled, onEditingChange, children, className,
}: EditableNumberProps) {
  const [local, setLocal] = useState(false)
  const editing = controlled ?? local
  const setEditing = (v: boolean) => { setLocal(v); onEditingChange?.(v) }
  const ref = useRef<HTMLSpanElement>(null)

  return (
    <span ref={ref} className={cx(s.cell, className)} data-editing={editing || undefined}>
      {editing ? (
        <EditInput
          initial={text}
          label={label}
          onCancel={() => setEditing(false)}
          onSubmit={draft => {
            const value = parse(draft)
            if (value === null) {
              onInvalid?.(draft)
              return
            }
            onCommit(value, ref.current?.getBoundingClientRect() ?? null)
            setEditing(false)
          }}
        />
      ) : (
        <button type="button" className={s.value} onClick={() => setEditing(true)} aria-label={`${label} ${text}，点击修改`}>
          <RollingNumber text={text} />
        </button>
      )}
      {children}
    </span>
  )
}

const NUMERIC = /^[-−]?\d+(\.\d+)?$/

export interface EditableTextProps {
  /** Current value as the backend reports it. */
  value: string
  label: string
  /** Called with the raw typed text (the backend parses it) and the cell's rect. */
  onCommit(value: string, rect: DOMRect | null): void
  editing?: boolean
  onEditingChange?(editing: boolean): void
  /** Disallow editing, e.g. read-only fields. */
  readOnly?: boolean
  children?: ReactNode
  className?: string
}

/**
 * Like EditableNumber, but commits text as typed: for field tables whose values can be
 * numbers, four-character ids or strings. Numeric values still roll when they change.
 */
export function EditableText({ value, label, onCommit, editing: controlled, onEditingChange, readOnly, children, className }: EditableTextProps) {
  const [local, setLocal] = useState(false)
  const editing = !readOnly && (controlled ?? local)
  const setEditing = (v: boolean) => { setLocal(v); onEditingChange?.(v) }
  const ref = useRef<HTMLSpanElement>(null)
  const shown = NUMERIC.test(value.trim()) ? <RollingNumber text={value.trim()} /> : <span className={s.text}>{value || '—'}</span>

  return (
    <span ref={ref} className={cx(s.cell, className)} data-editing={editing || undefined}>
      {editing ? (
        <EditInput
          initial={value}
          label={label}
          onCancel={() => setEditing(false)}
          onSubmit={draft => {
            onCommit(draft.trim(), ref.current?.getBoundingClientRect() ?? null)
            setEditing(false)
          }}
        />
      ) : readOnly ? (
        <span className={s.readOnly}>{shown}</span>
      ) : (
        <button type="button" className={s.value} onClick={() => setEditing(true)} aria-label={`${label} ${value}，点击修改`}>
          {shown}
        </button>
      )}
      {children}
    </span>
  )
}

function EditInput({ initial, label, onSubmit, onCancel }: {
  initial: string
  label: string
  onSubmit(draft: string): void
  onCancel(): void
}) {
  const [draft, setDraft] = useState(initial)
  return (
    <input
      className={s.input}
      autoFocus
      value={draft}
      aria-label={label}
      inputMode="decimal"
      onChange={e => setDraft(e.target.value)}
      onFocus={e => e.target.select()}
      onBlur={onCancel}
      onKeyDown={e => {
        if (e.key === 'Enter') { e.preventDefault(); onSubmit(draft) }
        else if (e.key === 'Escape') { e.preventDefault(); onCancel() }
      }}
    />
  )
}
