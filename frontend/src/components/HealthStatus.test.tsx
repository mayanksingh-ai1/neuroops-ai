import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { HealthStatus } from './HealthStatus'

afterEach(() => vi.unstubAllGlobals())

it('shows loading while a health request is pending', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
  render(<HealthStatus />)
  fireEvent.click(screen.getByRole('button', { name: 'Check API health' }))
  expect(screen.getByRole('status')).toHaveTextContent('Checking backend connection')
  expect(screen.getByRole('button')).toBeDisabled()
})

it('shows API success without claiming AI readiness', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }))
  render(<HealthStatus />)
  fireEvent.click(screen.getByRole('button'))
  expect(await screen.findByText(/API is responding. Database readiness is checked/)).toBeInTheDocument()
})

it('provides a retry action when the API cannot be reached', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
  render(<HealthStatus />)
  fireEvent.click(screen.getByRole('button'))
  expect(await screen.findByRole('button', { name: 'Retry connection' })).toBeEnabled()
  expect(screen.getByRole('status')).toHaveTextContent('Start the backend on port 8000')
})
