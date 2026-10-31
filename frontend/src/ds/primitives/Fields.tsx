import { forwardRef, useRef, type InputHTMLAttributes, type KeyboardEvent, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { Icon } from '../icons/Icon'
import { cx } from '../util'
import s from './Fields.module.css'

/* ---- Pills: filter chips borrowed from the Hearthstone card library ---- */

export interface PillOption<T extends string> {
  value: T
  label: string
  count?: number
}

/** Single-choice filter. Arrow keys move the choice, as in a radio group. */
export function PillGroup<T extends string>({ options, value, onChange, label, className }: {
  options: PillOption<T>[]
  value: T
  onChange(value: T): void
  label: string
  className?: string
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([])
  const onKeyDown = (e: KeyboardEvent, i: number) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    e.preventDefault()
    const next = (i + step + options.length) % options.length
    onChange(options[next].value)
    refs.current[next]?.focus()
  }
  return (
    <div className={cx(s.pills, className)} role="radiogroup" aria-label={label}>
      {options.map((o, i) => {
        const checked = o.value === value
        return (
          <button
            key={o.value}
            ref={el => { refs.current[i] = el }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            className={s.pill}
            onClick={() => onChange(o.value)}
            onKeyDown={e => onKeyDown(e, i)}
          >
            {o.label}
            {o.count !== undefined && <span className={s.count}>{o.count}</span>}
          </button>
        )
      })}
    </div>
  )
}

/* ---- Text fields ---- */

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Visible label; when omitted, pass aria-label. */
  label?: string
  /** search: pill-shaped with a magnifier. well: recessed rectangle. */
  variant?: 'well' | 'search'
  /** Short unit or hint after the input, e.g. "级". */
  suffix?: string
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, variant = 'well', suffix, className, ...rest },
  ref,
) {
  const field = (
    <span className={cx(s.field, s[variant], !label && className)}>
      {variant === 'search' && <Icon name="search" tone="muted" className={s.searchIcon} />}
      <input ref={ref} className={s.input} {...rest} />
      {suffix && <span className={s.suffix}>{suffix}</span>}
    </span>
  )
  if (!label) return field
  return (
    <label className={cx(s.labelled, className)}>
      <span className={s.label}>{label}</span>
      {field}
    </label>
  )
})

/* ---- Checkbox: square socket with a gold tick ---- */

export function Checkbox({ label, className, ...rest }: Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { label: string }) {
  return (
    <label className={cx(s.check, className)}>
      <input type="checkbox" className={s.checkInput} {...rest} />
      <span className={s.box} aria-hidden="true" />
      <span>{label}</span>
    </label>
  )
}

/* ---- Select: a recessed well with a bronze chevron; the list itself is the system's ---- */

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  options: { value: string; label: string }[]
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, options, className, ...rest },
  ref,
) {
  const field = (
    <span className={cx(s.field, s.well, s.selectWell, !label && className)}>
      <select ref={ref} className={s.select} {...rest}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </span>
  )
  if (!label) return field
  return (
    <label className={cx(s.labelled, className)}>
      <span className={s.label}>{label}</span>
      {field}
    </label>
  )
})

/* ---- Multi-line text: file paths, one per line ---- */

export const TextArea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string }>(function TextArea(
  { label, className, ...rest },
  ref,
) {
  const field = (
    <span className={cx(s.field, s.well, s.areaWell, !label && className)}>
      <textarea ref={ref} className={cx(s.input, s.area)} {...rest} />
    </span>
  )
  if (!label) return field
  return (
    <label className={cx(s.labelled, className)}>
      <span className={s.label}>{label}</span>
      {field}
    </label>
  )
})
