import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

// DEMO_ENABLED is computed at module load, so each test stubs env first and
// then imports a fresh copy of the module.
async function loadBanner() {
  vi.resetModules()
  return (await import('@/app/(dashboard)/controls/DemoBanner')).DemoBanner
}

afterEach(() => {
  cleanup()
  vi.unstubAllEnvs()
})

describe('DemoBanner', () => {
  it('renders nothing outside the demo deployment', async () => {
    vi.stubEnv('NEXT_PUBLIC_DEMO_EMAIL', '')
    vi.stubEnv('NEXT_PUBLIC_DEMO_PASSWORD', '')
    const DemoBanner = await loadBanner()

    const { container } = render(<DemoBanner onOpenControl={() => {}} />)
    expect(container.innerHTML).toBe('')
  })

  it('links to the CC8 control and can be dismissed in demo mode', async () => {
    vi.stubEnv('NEXT_PUBLIC_DEMO_EMAIL', 'demo@example.com')
    vi.stubEnv('NEXT_PUBLIC_DEMO_PASSWORD', 'demo-password')
    const DemoBanner = await loadBanner()
    const onOpenControl = vi.fn()

    render(<DemoBanner onOpenControl={onOpenControl} />)
    fireEvent.click(screen.getByRole('button', { name: /CC8-001/ }))
    expect(onOpenControl).toHaveBeenCalledOnce()

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByRole('button', { name: /CC8-001/ })).toBeNull()
  })
})
