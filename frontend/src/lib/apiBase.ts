/**
 * Single source of truth for the API base URL.
 *
 * In dev (Vite dev server on :5173):
 *   VITE_API_BASE_URL=http://localhost:8000  (set in .env)
 *   → full URL: http://localhost:8000/api/v1
 *
 * In production / installed app (FastAPI serves the frontend):
 *   VITE_API_BASE_URL is absent — falls back to empty string
 *   → relative URL: /api/v1  (resolves to same origin automatically)
 */
export const API_BASE = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1`;
export const API_ROOT = import.meta.env.VITE_API_BASE_URL ?? '';
