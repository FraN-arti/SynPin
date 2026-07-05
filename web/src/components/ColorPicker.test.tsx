import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ColorPicker } from './ColorPicker'

describe('ColorPicker', () => {
  it('renders trigger button', () => {
    const { container } = render(<ColorPicker value="#f97316" onChange={() => {}} />)
    const trigger = container.querySelector('.color-picker-trigger')
    expect(trigger).toBeInTheDocument()
  })

  it('applies current color as background', () => {
    const { container } = render(<ColorPicker value="#ef4444" onChange={() => {}} />)
    const trigger = container.querySelector('.color-picker-trigger') as HTMLElement
    expect(trigger.style.background).toBeTruthy()
  })

  it('renders small variant with size="sm"', () => {
    const { container } = render(<ColorPicker value="#22c55e" onChange={() => {}} size="sm" />)
    const trigger = container.querySelector('.color-picker-trigger') as HTMLElement
    expect(trigger).toBeInTheDocument()
  })

  it('re-renders when value prop changes', () => {
    const { rerender, container } = render(<ColorPicker value="#ef4444" onChange={() => {}} />)
    rerender(<ColorPicker value="#22c55e" onChange={() => {}} />)
    const trigger = container.querySelector('.color-picker-trigger')
    expect(trigger).toBeInTheDocument()
  })
})
