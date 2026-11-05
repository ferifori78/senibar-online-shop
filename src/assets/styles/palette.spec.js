import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const css = readFileSync(resolve(process.cwd(), 'src/assets/styles/globals.css'), 'utf8')

/** The value of a custom property as declared in globals.css. */
function token(name) {
  const match = css.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`))
  return match?.[1]
}

/** WCAG relative luminance. */
function luminance(hex) {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const [r, g, b] = channels.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

describe('palette contrast', () => {
  const paper = '#f4f1ea'
  const terminal = '#14110e'
  const raised = '#1e1a16'

  it('reads the tokens it is asserting on', () => {
    // Guards the regexes above: a renamed token would otherwise make every
    // assertion below silently pass on `undefined`.
    expect(token('--color-accent')).toBeTruthy()
    expect(token('--color-accent-terminal')).toBeTruthy()
  })

  it('carries the accent on paper at AA', () => {
    // A primary button is the one control a customer must be able to find.
    expect(contrast(token('--color-accent'), paper)).toBeGreaterThanOrEqual(4.5)
  })

  it('carries paper text on an accent fill at AA', () => {
    expect(contrast(paper, token('--color-accent'))).toBeGreaterThanOrEqual(4.5)
  })

  it('lifts the accent for the Terminal register', () => {
    // The Editorial green measures ~2.9:1 on a raised panel row and fails; the
    // panel therefore rebinds --accent rather than reusing it.
    const panelAccent = token('--color-accent-terminal')
    expect(contrast(panelAccent, terminal)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(panelAccent, raised)).toBeGreaterThanOrEqual(4.5)
  })

  it('keeps the ok lamp distinct from the accent', () => {
    // With the accent now green, a status lamp at the same hue would read as a
    // button. They must stay tellable apart.
    expect(token('--color-status-ok')).not.toBe(token('--color-accent'))
  })

  it('rebinds --accent inside the Terminal register', () => {
    // The mechanism itself: panel components say var(--accent) and must get
    // the lifted green without knowing which register they are in.
    expect(css).toMatch(/\.register-terminal\s*\{[^}]*--accent:\s*var\(--color-accent-terminal\)/s)
  })
})
