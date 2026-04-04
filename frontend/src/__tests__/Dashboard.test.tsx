import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Dashboard from '../pages/Dashboard'

function renderDashboard() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Dashboard metric cards', () => {
  it('renders the Total Portfolio Value metric label', () => {
    renderDashboard()
    expect(screen.getByText('Total Portfolio Value')).toBeInTheDocument()
  })

  it('renders the Unrealized PnL metric label', () => {
    renderDashboard()
    expect(screen.getByText('Unrealized PnL')).toBeInTheDocument()
  })

  it('renders the Active Agents metric label', () => {
    renderDashboard()
    expect(screen.getByText('Active Agents')).toBeInTheDocument()
  })

  it('renders the Risk Score metric label', () => {
    renderDashboard()
    expect(screen.getByText('Risk Score')).toBeInTheDocument()
  })
})
