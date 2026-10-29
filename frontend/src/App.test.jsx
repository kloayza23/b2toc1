import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReadingPassage, Vocabulary } from './App'

const apiMock = vi.fn()

vi.mock('./api', () => ({
  api: (...args) => apiMock(...args),
  session: { token: null },
}))

beforeEach(() => {
  apiMock.mockReset()
})

afterEach(cleanup)

describe('ReadingPassage', () => {
  const question = {
    id: 73,
    context: 'She stood in the ruined garden. The garden was quiet.',
  }

  it('permite seleccionar y guardar una palabra nueva', async () => {
    apiMock
      .mockResolvedValueOnce({ words: [] })
      .mockResolvedValueOnce({
        id: 9,
        question_id: 73,
        word: 'garden',
        status: 'learning',
      })
    const user = userEvent.setup()
    render(<ReadingPassage question={question} />)

    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/vocabulary?question_id=73'))
    await user.click(screen.getAllByRole('button', { name: 'garden' })[0])
    expect(screen.getByText('Nueva palabra seleccionada')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Aprender$/ }))

    await waitFor(() => expect(apiMock).toHaveBeenLastCalledWith('/vocabulary', {
      method: 'POST',
      body: JSON.stringify({ question_id: 73, word: 'garden', status: 'learning' }),
    }))
    expect(screen.getByText('1 guardadas')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'garden' })[0]).toHaveClass('learning')
  })

  it('restaura las palabras guardadas de esa lectura', async () => {
    apiMock.mockResolvedValueOnce({
      words: [{ id: 9, question_id: 73, word: 'garden', status: 'learned' }],
    })
    render(<ReadingPassage question={question} />)

    const words = await screen.findAllByRole('button', { name: 'garden' })
    expect(words).toHaveLength(2)
    words.forEach(word => expect(word).toHaveClass('learned'))
    expect(screen.getByText('1 guardadas')).toBeInTheDocument()
  })
})

describe('Vocabulary', () => {
  const overview = {
    total: 2,
    unique_words: 2,
    learning: 1,
    learned: 1,
    readings: [{ question_id: 73, level: 'B2', title: 'Lectura 1 · B2', total: 2, learning: 1, learned: 1 }],
    words: [
      { id: 9, question_id: 73, word: 'garden', status: 'learning', reading_title: 'Lectura 1 · B2' },
      { id: 10, question_id: 73, word: 'ruined', status: 'learned', reading_title: 'Lectura 1 · B2' },
    ],
  }

  it('muestra estadísticas por lectura y actualiza el estado de una palabra', async () => {
    apiMock
      .mockResolvedValueOnce(overview)
      .mockResolvedValueOnce({ ...overview.words[0], status: 'learned' })
    const user = userEvent.setup()
    render(<Vocabulary />)

    expect(await screen.findByRole('heading', { name: 'Vocabulario' })).toBeInTheDocument()
    expect(screen.getAllByText('Lectura 1 · B2')).toHaveLength(3)
    expect(screen.getByText('1/2')).toBeInTheDocument()
    const gardenRow = screen.getByText('garden').closest('.vocab-row')
    await user.click(within(gardenRow).getByRole('button', { name: 'Aprender' }))

    await waitFor(() => expect(apiMock).toHaveBeenLastCalledWith('/vocabulary/9', {
      method: 'PATCH',
      body: JSON.stringify({ status: 'learned' }),
    }))
    expect(screen.getByText('2/2')).toBeInTheDocument()
    expect(within(gardenRow).getByRole('button', { name: 'Aprendida' })).toBeInTheDocument()
  })
})
