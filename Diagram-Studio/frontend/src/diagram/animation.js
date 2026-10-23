// Turns an animation plan ({ entrance, flow, emphasis, speed, emphasize }) into CSS that lives inside the SVG,
// plus per-element props (class + animation-delay) for the renderer to spread onto its shapes.
//
// Rules that keep the exported file safe to open anywhere:
//  - No JavaScript and no SMIL: plain CSS animations only, so the SVG works as a file, in <img>, and in a page.
//  - The resting state is the finished diagram. Entrance effects run *from* hidden *to* the normal look, so a viewer that
//    ignores the CSS (or has reduced motion on) still shows the complete diagram.
//  - Extra effects (pulse rings, walkthrough highlights, flow dots) are overlays marked data-anim-only, hidden by default.
//  - Everything animated is marked data-anim / data-anim-only / data-anim-css, so the static SVG and the PNG can strip it all.

const SPEED = { slow: 1.6, normal: 1, fast: 0.6 }
const n2 = (v) => Math.round(v * 100) / 100

const none = () => ({})
const nothing = () => null

export const NO_ANIM = {
  css: '',
  group: none,
  node: none,
  edge: none,
  label: none,
  draw: none,
  flowEdge: nothing,
  ring: nothing,
  spot: nothing,
  part: none,
  msg: none,
  flowMsg: nothing,
  event: none,
  item: none,
}

/** The parts of a diagram a person can single out in a request ("make the database pulse"). */
export function animatableElements(spec) {
  if (spec.type === 'sequence') return spec.participants.map((p) => ({ id: p.id, label: p.label, focal: false }))
  if (spec.type === 'timeline') return spec.events.map((e, i) => ({ id: `e${i}`, label: e.label, focal: Boolean(e.focal) }))
  if (spec.type === 'quadrant') return spec.items.map((it, i) => ({ id: `i${i}`, label: it.label, focal: Boolean(it.focal) }))
  return spec.nodes.map((n) => ({ id: n.id, label: n.label, focal: n.kind === 'focal' }))
}

export function makeAnim(layout, plan, uid, t) {
  if (!plan) return NO_ANIM

  const k = SPEED[plan.speed] || 1
  const p = `a${uid}`
  const entering = plan.entrance !== 'none'
  const drawing = plan.entrance === 'draw' && layout.kind === 'graph'
  const dur = entering ? 0.5 * k : 0

  const at = { group: {}, node: {}, edge: [], label: [], part: {}, msg: [], event: [], item: [] }
  let end = 0
  const note = (delay) => {
    end = Math.max(end, delay + dur)
  }

  // ---- when does each element appear? (all zero when there is no entrance)
  let spotKeys = [] // walked through in order
  let ringKeys = [] // can pulse
  if (layout.kind === 'graph') {
    const count = layout.nodes.length + layout.groups.length
    const step = entering ? Math.min(0.3 * k, (4.5 * k) / Math.max(count, 1)) : 0
    layout.groups.forEach((g, i) => {
      at.group[g.id] = i * step * 0.6
      note(at.group[g.id])
    })
    const base = layout.groups.length ? layout.groups.length * step * 0.6 + step * 0.5 : 0
    layout.nodes.forEach((node, i) => {
      at.node[node.id] = base + i * step
      note(at.node[node.id])
    })
    layout.edges.forEach((edge, i) => {
      const d = (at.node[edge.from] ?? 0) + step * 0.6
      at.edge[i] = d
      at.label[i] = d + dur * 0.7
      note(at.label[i])
    })
    spotKeys = ringKeys = layout.nodes.map((node) => node.id)
  } else if (layout.kind === 'sequence') {
    const step = entering ? Math.min(0.4 * k, (6 * k) / Math.max(layout.messages.length, 1)) : 0
    layout.participants.forEach((part, i) => {
      at.part[part.id] = i * step * 0.5
      note(at.part[part.id])
    })
    const base = entering ? layout.participants.length * step * 0.5 + 0.2 : 0
    layout.messages.forEach((_, i) => {
      at.msg[i] = base + i * step
      note(at.msg[i])
    })
    spotKeys = layout.messages.map((_, i) => `m${i}`)
    ringKeys = layout.participants.map((part) => part.id)
  } else if (layout.kind === 'timeline') {
    const step = entering ? Math.min(0.45 * k, (5 * k) / Math.max(layout.events.length, 1)) : 0
    layout.events.forEach((_, i) => {
      at.event[i] = (entering ? 0.3 : 0) + i * step
      note(at.event[i])
    })
    spotKeys = ringKeys = layout.events.map((_, i) => `e${i}`)
  } else if (layout.kind === 'quadrant') {
    const step = entering ? Math.min(0.25 * k, (4 * k) / Math.max(layout.items.length, 1)) : 0
    layout.items.forEach((_, i) => {
      at.item[i] = (entering ? 0.3 : 0) + i * step
      note(at.item[i])
    })
    spotKeys = ringKeys = layout.items.map((_, i) => `i${i}`)
  }

  // Names the request singled out that actually exist on this diagram (a redraw may have removed some).
  const present = new Set(ringKeys)
  const emph = new Set((plan.emphasize || []).filter((id) => present.has(id)))

  // ---- walkthrough: each element is lit for `spotLen` seconds, then the loop repeats
  const spotLen = 1.1 * k
  const cycle = Math.max(spotKeys.length, 1) * spotLen + 1.2 * k
  const lit = n2((spotLen / cycle) * 100)
  const rise = n2(Math.min(3, lit / 2))
  const fadeOut = n2(Math.min(lit + 4, 99))
  const order = new Map(spotKeys.map((key, i) => [key, i]))

  const accent = t.accent
  const css = `
@keyframes ${p}-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes ${p}-fade{from{opacity:0}to{opacity:1}}
@keyframes ${p}-draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
@keyframes ${p}-flowin{from{opacity:0}to{opacity:.95}}
@keyframes ${p}-flow{to{stroke-dashoffset:-24.1}}
@keyframes ${p}-ping{0%{opacity:.6;transform:scale(1)}70%,100%{opacity:0;transform:scale(1.2)}}
@keyframes ${p}-spot{0%{opacity:0}${rise}%,${lit}%{opacity:1}${fadeOut}%,100%{opacity:0}}
.${p}-in{animation:${p}-in ${n2(dur)}s cubic-bezier(.2,.7,.2,1) both}
.${p}-fade{animation:${p}-fade ${n2(dur)}s ease both}
.${p}-draw{stroke-dasharray:1;animation:${p}-draw ${n2(dur)}s ease-out both}
.${p}-ring{fill:none;stroke:${accent};stroke-width:1.5;opacity:0;transform-box:fill-box;transform-origin:center;pointer-events:none;animation:${p}-ping ${n2(2.4 * k)}s ease-out infinite}
.${p}-spot{fill:none;stroke:${accent};stroke-width:2;opacity:0;pointer-events:none;animation:${p}-spot ${n2(cycle)}s linear infinite}
.${p}-flow{fill:none;stroke:${accent};stroke-width:2.4;stroke-linecap:round;stroke-dasharray:.1 24;opacity:0;pointer-events:none;animation:${p}-flowin .5s ease both,${p}-flow ${n2(0.7 * k)}s linear infinite}
@media (prefers-reduced-motion:reduce){.${p}-in,.${p}-fade,.${p}-draw,.${p}-ring,.${p}-spot,.${p}-flow{animation:none!important}}
`.trim()

  const enter = (delay, kind = 'in') =>
    entering ? { className: `${p}-${kind}`, 'data-anim': true, style: { animationDelay: `${n2(delay ?? 0)}s` } } : {}
  const overlay = (name, delay) => ({ className: `${p}-${name}`, 'data-anim-only': true, style: { animationDelay: `${n2(delay)}s` } })
  const flowAt = (delay) => (plan.flow ? overlay('flow', delay + dur) : null)

  return {
    css,
    group: (id) => enter(at.group[id]),
    node: (id) => enter(at.node[id]),
    edge: (i) => enter(at.edge[i], 'fade'),
    label: (i) => enter(at.label[i], 'fade'),
    // The line draws itself; only for solid lines, since a dashed line already uses the dash pattern.
    draw: (i, solid) =>
      entering && drawing && solid
        ? { className: `${p}-draw`, 'data-anim': true, pathLength: 1, style: { animationDelay: `${n2(at.edge[i] ?? 0)}s` } }
        : {},
    flowEdge: (i) => flowAt(at.edge[i] ?? 0),
    // Pulse: the parts the request named, or else the diagram's own focal parts.
    ring: (key, focal) => (plan.emphasis === 'pulse' && (emph.size ? emph.has(key) : focal) ? overlay('ring', end + 0.3) : null),
    spot: (key) => (plan.emphasis === 'walkthrough' && order.has(key) ? overlay('spot', end + 0.5 + order.get(key) * spotLen) : null),
    part: (id) => enter(at.part[id]),
    msg: (i) => enter(at.msg[i], 'fade'),
    flowMsg: (i) => flowAt(at.msg[i] ?? 0),
    event: (i) => enter(at.event[i]),
    item: (i) => enter(at.item[i]),
  }
}
