// How model-written Markdown is rendered: as UNTRUSTED text. No raw HTML, no images, no scripts; a link may only go to http, https or
// mailto, carries no referrer or opener, and opens in a new tab. Anything the server says is shown as text, never as HTML.
const SAFE_LINK = /^(https?:|mailto:)/i

export function safeHref(href: string | undefined): string | null {
  if (!href) return null
  const trimmed = href.trim().replace(/[\u0000-\u001f\u007f\s]+/g, '')
  return SAFE_LINK.test(trimmed) ? href.trim() : null
}

// react-markdown skips raw HTML by default (we never enable the plugin that allows it); these are the elements we refuse as well.
export const DISALLOWED_ELEMENTS = ['img', 'script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'link', 'meta'] as const
