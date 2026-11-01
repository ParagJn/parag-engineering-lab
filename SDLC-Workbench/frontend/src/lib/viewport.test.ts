import { describe, expect, it } from 'vitest'
import { BUTTON_COMMAND, MAX_SCALE, MIN_SCALE, STEP, apply, clampScale, closesFullScreen, commandForKey, fit, keepReachable, pageScroll, pan, percent, sizeOf, wheelFactor, zoomAt } from './viewport'

describe('fit', () => {
  it('shows a large picture whole, centred, smaller than natural size', () => {
    const v = fit({ width: 800, height: 600 }, { width: 1600, height: 1000 })
    expect(v.scale).toBeCloseTo(0.48, 6)                                   // across: (800 - 32) / 1600 = 0.48; down: (600 - 32) / 1000 = 0.568; the tighter one wins
    expect(v.x + 1600 * v.scale / 2).toBeCloseTo(400, 6); expect(v.y + 1000 * v.scale / 2).toBeCloseTo(300, 6)
  })
  it('does not blow a small picture up past natural size unless asked', () => {
    expect(fit({ width: 800, height: 600 }, { width: 200, height: 100 }).scale).toBe(1)
    expect(fit({ width: 800, height: 600 }, { width: 200, height: 100 }, 16, true).scale).toBeCloseTo(3.84, 2)
  })
  it('leaves the margin on every side', () => {
    const v = fit({ width: 1000, height: 1000 }, { width: 2000, height: 2000 }, 50)
    expect(2000 * v.scale).toBeCloseTo(900, 6)
  })
  it('answers a neutral view for a frame or picture with no size, never NaN', () => {
    for (const [f, c] of [[{ width: 0, height: 0 }, { width: 10, height: 10 }], [{ width: 10, height: 10 }, { width: 0, height: 5 }]] as const) {
      expect(fit(f, c)).toEqual({ scale: 1, x: 0, y: 0 })
    }
  })
})

describe('zoomAt', () => {
  it('keeps the point under the pointer where it is', () => {
    const before = { scale: 1, x: 40, y: 30 }
    const after = zoomAt(before, 2, 300, 200)
    // the picture point under (300, 200) before is ((300 - 40) / 1, (200 - 30) / 1); after, it must still be under (300, 200)
    expect((300 - after.x) / after.scale).toBeCloseTo((300 - before.x) / before.scale, 9)
    expect((200 - after.y) / after.scale).toBeCloseTo((200 - before.y) / before.scale, 9)
    expect(after.scale).toBe(2)
  })
  it('zooming out does the same', () => {
    const after = zoomAt({ scale: 2, x: -100, y: -50 }, 0.5, 120, 80)
    expect((120 - after.x) / after.scale).toBeCloseTo((120 + 100) / 2, 9)
  })
  it('never goes past the limits, and a view at the limit does not move when pushed further', () => {
    expect(zoomAt({ scale: 1, x: 0, y: 0 }, 1000, 0, 0).scale).toBe(MAX_SCALE)
    expect(zoomAt({ scale: 1, x: 0, y: 0 }, 0.0001, 0, 0).scale).toBe(MIN_SCALE)
    const atMax = { scale: MAX_SCALE, x: 10, y: 20 }
    expect(zoomAt(atMax, 2, 99, 99)).toEqual(atMax)
  })
  it('the limits are these numbers', () => { expect([MIN_SCALE, MAX_SCALE, STEP]).toEqual([0.1, 8, 1.25]) })
})

describe('pan and reach', () => {
  it('moving by (dx, dy) moves the picture by exactly that and keeps its scale', () => {
    expect(pan({ scale: 1.5, x: 10, y: 20 }, 7, -3)).toEqual({ scale: 1.5, x: 17, y: 17 })
  })
  it('a picture cannot be dragged out of reach', () => {
    const frame = { width: 400, height: 300 }; const content = { width: 1000, height: 800 }
    const far = keepReachable({ scale: 1, x: 5000, y: 5000 }, frame, content)
    expect(far.x).toBe(352); expect(far.y).toBe(252)                                // 48 pixels of it stay in the frame at the right and bottom
    const gone = keepReachable({ scale: 1, x: -9000, y: -9000 }, frame, content)
    expect(gone.x).toBe(48 - 1000); expect(gone.y).toBe(48 - 800)
  })
  it('a view already in reach is left alone', () => {
    const v = { scale: 0.5, x: 20, y: 30 }
    expect(keepReachable(v, { width: 400, height: 300 }, { width: 600, height: 400 })).toEqual(v)
  })
})

describe('the small helpers', () => {
  it('clampScale holds a number inside the limits and answers 1 for anything that is not a number', () => {
    expect(clampScale(0)).toBe(MIN_SCALE); expect(clampScale(99)).toBe(MAX_SCALE); expect(clampScale(2)).toBe(2)
    expect(clampScale(NaN)).toBe(1); expect(clampScale(Infinity)).toBe(1)
  })
  it('a wheel notch up zooms in by one step, down zooms out by one step, no turn changes nothing', () => {
    expect(wheelFactor(-120)).toBe(1.25); expect(wheelFactor(120)).toBe(0.8); expect(wheelFactor(0)).toBe(1); expect(wheelFactor(NaN)).toBe(1)
    expect(wheelFactor(-1)).toBe(wheelFactor(-1000))                                // the size of the turn does not matter
  })
  it('percent is the scale as a whole number', () => {
    expect(percent({ scale: 1, x: 0, y: 0 })).toBe('100%'); expect(percent({ scale: 0.484, x: 0, y: 0 })).toBe('48%'); expect(percent({ scale: 2.5, x: 0, y: 0 })).toBe('250%')
  })
  it('sizeOf reads the viewBox and nothing else', () => {
    expect(sizeOf('<svg viewBox="0 0 1240 678" width="9">')).toEqual({ width: 1240, height: 678 })
    expect(sizeOf('<svg viewBox="-10 -20 300.5 100">')).toEqual({ width: 300.5, height: 100 })
    expect(sizeOf('<svg width="10" height="10">')).toBeNull(); expect(sizeOf('<svg viewBox="0 0 0 5">')).toBeNull(); expect(sizeOf('')).toBeNull()
  })
})

describe('the keys', () => {
  it('plus and equals zoom in, minus zooms out, zero fits', () => {
    expect(commandForKey('+')).toEqual({ kind: 'zoom', factor: 1.25 }); expect(commandForKey('=')).toEqual({ kind: 'zoom', factor: 1.25 })
    expect(commandForKey('-')).toEqual({ kind: 'zoom', factor: 0.8 }); expect(commandForKey('0')).toEqual({ kind: 'fit' })
  })
  it('each arrow moves the picture by one step in its own direction', () => {
    expect(commandForKey('ArrowLeft')).toEqual({ kind: 'move', dx: 40, dy: 0 }); expect(commandForKey('ArrowRight')).toEqual({ kind: 'move', dx: -40, dy: 0 })
    expect(commandForKey('ArrowUp')).toEqual({ kind: 'move', dx: 0, dy: 40 }); expect(commandForKey('ArrowDown')).toEqual({ kind: 'move', dx: 0, dy: -40 })
    expect(commandForKey('ArrowUp', 10)).toEqual({ kind: 'move', dx: 0, dy: 10 })
  })
  it('any other key is not ours, so Tab and the rest keep working', () => {
    for (const key of ['Tab', 'Enter', ' ', 'a', 'Escape', '1', 'Shift']) expect(commandForKey(key)).toBeNull()
  })
})

describe('applying a command', () => {
  const frame = { width: 800, height: 600 }; const content = { width: 1600, height: 1000 }
  it('fit gives the fitted view whatever the view was', () => {
    expect(apply({ kind: 'fit' }, { scale: 3, x: 99, y: 99 }, frame, content)).toEqual(fit(frame, content))
  })
  it('a zoom keeps the middle of the frame where it is', () => {
    const v = apply({ kind: 'zoom', factor: 2 }, { scale: 1, x: 100, y: 50 }, frame, content)
    expect(v.scale).toBe(2); expect((400 - v.x) / v.scale).toBeCloseTo((400 - 100) / 1, 9); expect((300 - v.y) / v.scale).toBeCloseTo((300 - 50) / 1, 9)
  })
  it('a zoom cannot take the picture out of reach either', () => {
    // a picture dragged almost out of the frame, then zoomed in on the middle: the result must still leave 48 pixels of it inside
    const v = apply({ kind: 'zoom', factor: 8 }, { scale: 1, x: 790, y: 590 }, frame, content)
    expect(v.x).toBeLessThanOrEqual(frame.width - 48); expect(v.y).toBeLessThanOrEqual(frame.height - 48)
    expect(v.x + content.width * v.scale).toBeGreaterThanOrEqual(48); expect(v.y + content.height * v.scale).toBeGreaterThanOrEqual(48)
  })
  it('a move changes the position by the step and not the scale', () => {
    expect(apply({ kind: 'move', dx: 40, dy: -40 }, { scale: 1, x: 0, y: 0 }, frame, content)).toEqual({ scale: 1, x: 40, y: -40 })
  })
  it('a move cannot take the picture out of reach', () => {
    expect(apply({ kind: 'move', dx: 100000, dy: 0 }, { scale: 1, x: 0, y: 0 }, frame, content).x).toBe(800 - 48)
  })
})

describe('the buttons', () => {
  it('zoom in zooms in, zoom out zooms out, fit fits, full opens full screen', () => {
    expect(BUTTON_COMMAND).toEqual({ zoomIn: { kind: 'zoom', factor: 1.25 }, zoomOut: { kind: 'zoom', factor: 0.8 }, fit: { kind: 'fit' }, full: 'full' })
  })
  it('the buttons do what the keys do', () => {
    expect(BUTTON_COMMAND.zoomIn).toEqual(commandForKey('+')); expect(BUTTON_COMMAND.zoomOut).toEqual(commandForKey('-')); expect(BUTTON_COMMAND.fit).toEqual(commandForKey('0'))
  })
})

describe('full screen', () => {
  it('only Escape closes it', () => {
    expect(closesFullScreen('Escape')).toBe(true)
    for (const key of ['Enter', 'q', 'F11', ' ', 'Esc']) expect(closesFullScreen(key)).toBe(false)
  })
  it('locks the page behind from scrolling and gives back exactly what it had', () => {
    const style = { overflow: 'auto' }
    const unlock = pageScroll(style).lock()
    expect(style.overflow).toBe('hidden'); unlock(); expect(style.overflow).toBe('auto')
    const empty = { overflow: '' }; const again = pageScroll(empty).lock(); expect(empty.overflow).toBe('hidden'); again(); expect(empty.overflow).toBe('')
  })
})
