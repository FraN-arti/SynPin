import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { LoadingSpinner } from './LoadingSpinner'

describe('LoadingSpinner', () => {
  it('renders text when provided', () => {
    render(<LoadingSpinner text="Loading data..." />)
    expect(screen.getByText('Loading data...')).toBeInTheDocument()
  })

  it('renders without text', () => {
    const { container } = render(<LoadingSpinner />)
    expect(container.querySelector('.loading-spinner')).toBeInTheDocument()
    expect(container.querySelector('.loading-text')).toBeNull()
  })

  it('applies custom minHeight', () => {
    const { container } = render(<LoadingSpinner text="Loading" minHeight={60} />)
    const wrapper = container.querySelector('.loading-spinner') as HTMLElement
    expect(wrapper.style.minHeight).toBe('60px')
  })

  it('has spinner ring element', () => {
    const { container } = render(<LoadingSpinner />)
    expect(container.querySelector('.loading-ring')).toBeInTheDocument()
  })
})
