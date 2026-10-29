import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

Object.defineProperty(window, 'speechSynthesis', {
  configurable: true,
  value: { cancel: vi.fn(), speak: vi.fn() },
})

globalThis.SpeechSynthesisUtterance = class SpeechSynthesisUtterance {
  constructor(text) {
    this.text = text
  }
}
