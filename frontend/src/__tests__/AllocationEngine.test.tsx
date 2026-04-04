import { render, screen, fireEvent, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AllocationEngine from '../pages/AllocationEngine'

function renderAllocationEngine() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AllocationEngine />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('AllocationEngine', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders the Simulate button in idle state', () => {
    renderAllocationEngine()
    expect(screen.getByText('Simulate')).toBeInTheDocument()
  })

  it('clicking Simulate toggles button to Running state', () => {
    renderAllocationEngine()
    const btn = screen.getByText('Simulate')
    fireEvent.click(btn)
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('clicking Running button toggles back to Simulate', () => {
    renderAllocationEngine()
    const btn = screen.getByText('Simulate')
    fireEvent.click(btn)
    expect(screen.getByText('Running')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Running'))
    expect(screen.getByText('Simulate')).toBeInTheDocument()
  })

  it('weights update after simulation steps', () => {
    renderAllocationEngine()
    fireEvent.click(screen.getByText('Simulate'))
    act(() => {
      vi.advanceTimersByTime(800)
    })
    expect(screen.getByText('1')).toBeInTheDocument()
  })
})
