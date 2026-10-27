import { getCookie, setCookie } from './cookies'

const COOKIE_NAME = 'client_id'
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 5 // 5 years in seconds

export function getOrCreateClientId(): string {
  let id = getCookie(COOKIE_NAME)
  if (!id) {
    id = crypto.randomUUID()
    setCookie(COOKIE_NAME, id, COOKIE_MAX_AGE)
  }
  return id
}
