import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Landing from '../pages/Landing'

function renderLanding() {
  return render(
    <MemoryRouter>
      <Landing />
    </MemoryRouter>
  )
}

describe('Landing page', () => {
  it('renders the hero heading', () => {
    renderLanding()
<<<<<<< HEAD
    expect(screen.getByText('Built for the curious')).toBeInTheDocument()
    expect(screen.getByText('Asme')).toBeInTheDocument()
  })

  it('renders the "Manifesto" button', () => {
    renderLanding()
    expect(screen.getByRole('button', { name: /manifesto/i })).toBeInTheDocument()
=======
    expect(screen.getByText('Autonomous Capital')).toBeInTheDocument()
    expect(screen.getByText('Allocation Protocol')).toBeInTheDocument()
  })

  it('renders the "Enter App" button', () => {
    renderLanding()
    expect(screen.getByRole('button', { name: /enter app/i })).toBeInTheDocument()
>>>>>>> D!
  })
})
