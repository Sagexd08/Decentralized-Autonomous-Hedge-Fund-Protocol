import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Agents from '../pages/Agents'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

function renderAgents() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Agents />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Agents page', () => {
  beforeEach(() => mockNavigate.mockClear())

  it('renders agent cards with agent names visible', () => {
    renderAgents()

    expect(screen.getByText('AlphaWave')).toBeInTheDocument()
    expect(screen.getByText('NeuralArb')).toBeInTheDocument()
  })

  it('filters agent cards when typing in the search box', () => {
    renderAgents()
    const input = screen.getByPlaceholderText('Search agents...')
    fireEvent.change(input, { target: { value: 'AlphaWave' } })
    expect(screen.getByText('AlphaWave')).toBeInTheDocument()
    expect(screen.queryByText('NeuralArb')).not.toBeInTheDocument()
  })

  it('navigates to agent detail page when clicking an agent card', () => {
    renderAgents()
    fireEvent.click(screen.getByText('AlphaWave'))
    expect(mockNavigate).toHaveBeenCalledWith('/agents/AGT-001')
  })
})
