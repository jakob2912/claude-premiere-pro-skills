// Phone mockup geometry + camera moves for reel scenes
window.Phone = {
  RATIO: 2556 / 1180, // iPhone screen recording
  BEZEL: 14,
  // lay out a phone at (left, top) with screen width sw
  place(el, left, top, sw) {
    const g = { left, top, sw, sh: Math.round(sw * this.RATIO), b: this.BEZEL };
    el.style.left = left + "px";
    el.style.top = top + "px";
    const scr = el.querySelector(".screen");
    scr.style.width = g.sw + "px";
    scr.style.height = g.sh + "px";
    g.w = g.sw + 2 * g.b; g.h = g.sh + 2 * g.b;
    return g;
  },
  // set the camera (.cam, transform-origin 0 0) so screen point (fx, fy) lands on (tx, ty) at zoom s
  focus(g, fx, fy, s, tx = 540, ty = 760) {
    const px = g.left + g.b + fx * g.sw, py = g.top + g.b + fy * g.sh;
    return { x: tx - px * s, y: ty - py * s, scale: s };
  },
  // screen point in stage coordinates for a given camera
  toStage(g, fx, fy, cam) {
    return { x: cam.x + (g.left + g.b + fx * g.sw) * cam.scale, y: cam.y + (g.top + g.b + fy * g.sh) * cam.scale };
  },
};
