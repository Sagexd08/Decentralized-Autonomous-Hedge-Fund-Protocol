/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_WS_TRADING_URL?: string
  readonly VITE_WS_PRICES_URL?: string
  readonly VITE_WS_MARKET_URL?: string
  readonly VITE_WS_SOCIAL_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
