import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { Toggle } from './Toggle'

describe('Toggle', () => {
  it('renders label text', () => {
    render(<Toggle label="Enable feature" onChange={() => {}} />)
    expect(screen.getByText('Enable feature')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(<Toggle label="Feature" description="Some explanation" onChange={() => {}} />)
    expect(screen.getByText('Some explanation')).toBeInTheDocument()
  })

  it('does not render description when omitted', () => {
    const { container } = render(<Toggle label="Feature" onChange={() => {}} />)
    expect(container.querySelector('.settings-toggle-desc')).toBeNull()
  })

  it('calls onChange with checked value on click', async () => {
    const onChange = vi.fn()
    render(<Toggle label="Feature" onChange={onChange} />)
    const checkbox = screen.getByRole('checkbox')
    await userEvent.click(checkbox)
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('respects controlled checked prop', () => {
    render(<Toggle label="Feature" checked={true} onChange={() => {}} />)
    expect(screen.getByRole('checkbox')).toBeChecked()
  })

  it('renders unchecked when checked=false', () => {
    render(<Toggle label="Feature" checked={false} onChange={() => {}} />)
    expect(screen.getByRole('checkbox')).not.toBeChecked()
  })
})
