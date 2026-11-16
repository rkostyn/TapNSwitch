import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { VenueLayout } from '../api'

const getVenue = vi.fn<() => Promise<VenueLayout>>()
vi.mock('../api', () => ({ getVenue: () => getVenue() }))

const layout: VenueLayout = {
  venue: 'Baltimore Urban Axes',
  arenas: [
    { arena_id: 'red', name: 'Red', color: '#dc2626', text_color: '#ffffff', lanes: [{ lane_id: 'red-1', label: 'Lane 1' }, { lane_id: 'red-2', label: 'Lane 2' }] },
    { arena_id: 'white', name: 'White', color: '#e5e7eb', text_color: '#111827', lanes: [{ lane_id: 'white-1', label: 'Lane 1' }] },
  ],
}

// Fresh module (and store) per test
async function load() {
  vi.resetModules()
  return import('../venue')
}

describe('venue store', () => {
  beforeEach(() => {
    getVenue.mockReset()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('falls back to raw ids before the layout loads', async () => {
    const v = await load()
    expect(v.arenaById('red')).toBeUndefined()
    expect(v.arenaLabel(['red', 'blue'])).toBe('red / blue')
    expect(v.laneLabel('red-1')).toBe('red-1')
    expect(v.laneLabel(null)).toBe('')
    expect(v.arenaLabel([])).toBe('')
  })

  it('labels arenas and lanes once loaded', async () => {
    getVenue.mockResolvedValue(layout)
    const v = await load()
    await v.loadVenue()
    expect(v.venue.name).toBe('Baltimore Urban Axes')
    expect(v.arenaById('white')?.color).toBe('#e5e7eb')
    expect(v.arenaLabel(['red', 'white', 'mystery'])).toBe('Red / White / mystery')
    expect(v.laneLabel('red-2')).toBe('Red · Lane 2')
    // Unknown lane number on a known arena, and a bare arena id
    expect(v.laneLabel('white-3')).toBe('White · Lane 3')
    expect(v.laneLabel('red')).toBe('Red')
    expect(v.laneLabel('nowhere-1')).toBe('nowhere-1')
  })

  it('logs a failed load, keeps raw ids, and can retry', async () => {
    getVenue.mockRejectedValueOnce(new Error('404'))
    const v = await load()
    await expect(v.loadVenue()).resolves.toBeUndefined()
    expect(console.error).toHaveBeenCalled()
    expect(v.arenaLabel(['red'])).toBe('red')

    getVenue.mockResolvedValue(layout)
    await v.loadVenue()
    expect(v.arenaLabel(['red'])).toBe('Red')
  })

  it('loads only once', async () => {
    getVenue.mockResolvedValue(layout)
    const v = await load()
    await Promise.all([v.loadVenue(), v.loadVenue()])
    await v.loadVenue()
    expect(getVenue).toHaveBeenCalledTimes(1)
  })
})
