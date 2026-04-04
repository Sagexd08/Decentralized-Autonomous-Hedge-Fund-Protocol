import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export const WS_TRADING_URL = import.meta.env.VITE_WS_TRADING_URL || 'ws://localhost:8000/ws/trading'
export const WS_PRICES_URL = import.meta.env.VITE_WS_PRICES_URL || 'ws://localhost:8000/ws/prices'
export const WS_MARKET_URL = import.meta.env.VITE_WS_MARKET_URL || 'ws://localhost:8000/ws/market'
export const WS_SOCIAL_URL = import.meta.env.VITE_WS_SOCIAL_URL || 'ws://localhost:8000/ws/social'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})
