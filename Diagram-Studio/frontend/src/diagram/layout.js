import { ensureFonts, textWidth } from './measure'
import { FONT, TYPE } from './theme'
import { layoutGraph } from './graphLayout'
import { layoutQuadrant, layoutSequence, layoutTimeline } from './otherLayouts'

/** Turn a validated diagram spec into positioned geometry. Independent of colours, so theme switches are free. */
export async function layoutDiagram(spec) {
  await ensureFonts()
  let body
  switch (spec.type) {
    case 'architecture':
    case 'flowchart':
    case 'state':
      body = await layoutGraph(spec)
      break
    case 'sequence':
      body = layoutSequence(spec)
      break
    case 'timeline':
      body = layoutTimeline(spec)
      break
    case 'quadrant':
      body = layoutQuadrant(spec)
      break
    default:
      throw new Error(`Unknown diagram type '${spec.type}'.`)
  }
  return {
    ...body,
    type: spec.type,
    title: spec.title,
    subtitle: spec.subtitle,
    titleW: textWidth(spec.title, TYPE.title, FONT.serif),
    subtitleW: spec.subtitle ? textWidth(spec.subtitle, TYPE.subtitle, FONT.sans) : 0,
  }
}
