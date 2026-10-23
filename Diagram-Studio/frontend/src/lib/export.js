const FONT_CSS_URL =
  'https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&family=Instrument+Serif&display=swap'

let fontCssPromise = null

function toDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

/**
 * @font-face rules with the latin subset inlined as data URLs, so an exported SVG or PNG looks the same
 * on a machine that does not have Geist / Instrument Serif. Falls back to '' (system fonts) when offline.
 */
function embeddedFontCss() {
  if (!fontCssPromise) {
    fontCssPromise = (async () => {
      try {
        const css = await (await fetch(FONT_CSS_URL)).text()
        const blocks = [...css.matchAll(/\/\*\s*([\w-]+)\s*\*\/\s*(@font-face\s*\{[^}]*\})/g)].filter((m) => m[1] === 'latin').map((m) => m[2])
        const inlined = await Promise.all(
          blocks.map(async (block) => {
            const match = block.match(/url\((https:[^)]+)\)/)
            if (!match) return block
            const data = await toDataUrl(await (await fetch(match[1])).blob())
            return block.replace(match[1], data)
          }),
        )
        return inlined.join('\n')
      } catch {
        fontCssPromise = null
        return ''
      }
    })()
  }
  return fontCssPromise
}

/** Remove every animation hook so what is left is the finished diagram. */
function stripAnimation(root) {
  root.querySelectorAll('[data-anim-only]').forEach((el) => el.remove())
  root.querySelectorAll('style[data-anim-css]').forEach((el) => el.remove())
  root.querySelectorAll('[data-anim]').forEach((el) => {
    el.removeAttribute('class')
    el.removeAttribute('style')
    el.removeAttribute('pathLength')
  })
}

async function serialize(svg, { animated = false } = {}) {
  const clone = svg.cloneNode(true)
  clone.removeAttribute('style')
  clone.removeAttribute('role')
  clone.removeAttribute('data-diagram')
  if (!animated) stripAnimation(clone)
  clone.querySelectorAll('[data-anim]').forEach((el) => el.removeAttribute('data-anim'))
  clone.querySelectorAll('[data-anim-only]').forEach((el) => el.removeAttribute('data-anim-only'))
  const fontCss = await embeddedFontCss()
  if (fontCss) {
    const style = document.createElementNS('http://www.w3.org/2000/svg', 'style')
    style.textContent = fontCss
    clone.insertBefore(style, clone.firstChild)
  }
  return {
    markup: `<?xml version="1.0" encoding="UTF-8"?>\n${new XMLSerializer().serializeToString(clone)}`,
    width: Number(clone.getAttribute('width')),
    height: Number(clone.getAttribute('height')),
  }
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const fileSafe = (name) =>
  String(name || 'diagram')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'diagram'

export async function downloadSvg(svg, name, { animated = false } = {}) {
  const { markup } = await serialize(svg, { animated })
  download(new Blob([markup], { type: 'image/svg+xml;charset=utf-8' }), `${fileSafe(name)}${animated ? '-animated' : ''}.svg`)
}

// A PNG is one frame, so it is always the finished, static diagram.
export async function downloadPng(svg, name, scale = 2) {
  const { markup, width, height } = await serialize(svg)
  const url = URL.createObjectURL(new Blob([markup], { type: 'image/svg+xml;charset=utf-8' }))
  try {
    const image = new Image()
    image.decoding = 'sync'
    await new Promise((resolve, reject) => {
      image.onload = resolve
      image.onerror = () => reject(new Error('The diagram could not be turned into an image.'))
      image.src = url
    })
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(width * scale)
    canvas.height = Math.round(height * scale)
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)
    ctx.drawImage(image, 0, 0, width, height)
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
    if (!blob) throw new Error('The PNG could not be created.')
    download(blob, `${fileSafe(name)}.png`)
  } finally {
    URL.revokeObjectURL(url)
  }
}
