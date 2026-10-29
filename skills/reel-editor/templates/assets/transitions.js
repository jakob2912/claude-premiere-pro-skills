// Transition library for brand films. Each function gets the GSAP timeline, the layers of the
// transition (A = outgoing shot, B = incoming, fx = light/flash, blur = SVG directional blur)
// and the times: t0 = start, c = cut, d = duration. A and B are only visible within [t0, t0+d].
window.Transitions = {
  dissolve(tl, e, t0, c, d) {
    tl.fromTo(e.b, { opacity: 0 }, { opacity: 1, duration: d, ease: "sine.inOut" }, t0);
  },
  blurdissolve(tl, e, t0, c, d) {
    tl.fromTo(e.a, { filter: "blur(0px)", scale: 1.0 }, { filter: "blur(16px)", scale: 1.05, duration: d, ease: "power2.inOut" }, t0);
    tl.fromTo(e.b, { opacity: 0, filter: "blur(16px)", scale: 1.05 },
      { opacity: 1, filter: "blur(0px)", scale: 1.0, duration: d, ease: "power2.inOut" }, t0);
  },
  bloom(tl, e, t0, c, d) {
    const h = d / 2;
    tl.fromTo(e.a, { filter: "brightness(1)" }, { filter: "brightness(1.8)", duration: h, ease: "power2.in" }, t0);
    tl.fromTo(e.fx, { opacity: 0 }, { opacity: 0.92, duration: h, ease: "power2.in" }, t0);
    tl.set(e.b, { opacity: 1, filter: "brightness(1.8)" }, c);
    tl.to(e.fx, { opacity: 0, duration: h, ease: "power2.out" }, c);
    tl.to(e.b, { filter: "brightness(1)", duration: h, ease: "power2.out" }, c);
  },
  zoomthrough(tl, e, t0, c, d) {
    const h = d / 2;
    tl.fromTo(e.a, { scale: 1, filter: "blur(0px)" }, { scale: 1.35, filter: "blur(18px)", duration: h, ease: "power3.in" }, t0);
    tl.set(e.b, { opacity: 1 }, c);
    tl.fromTo(e.b, { scale: 1.28, filter: "blur(18px)" }, { scale: 1, filter: "blur(0px)", duration: h, ease: "power3.out" }, c);
  },
  slideup(tl, e, t0, c, d) { this._slide(tl, e, t0, c, d, 0, -1); },
  slidedown(tl, e, t0, c, d) { this._slide(tl, e, t0, c, d, 0, 1); },
  whipleft(tl, e, t0, c, d) { this._slide(tl, e, t0, c, d, -1, 0); },
  whipright(tl, e, t0, c, d) { this._slide(tl, e, t0, c, d, 1, 0); },
  _slide(tl, e, t0, c, d, dx, dy) {
    // push transition with motion blur in the direction of travel (whip pan)
    const W = 1080, H = 1920, amt = dx ? "60 0" : "0 70";
    tl.set(e.b, { opacity: 1, x: -dx * W, y: -dy * H }, t0);
    tl.fromTo([e.a, e.b], { x: (i) => (i ? -dx * W : 0), y: (i) => (i ? -dy * H : 0) },
      { x: (i) => (i ? 0 : dx * W), y: (i) => (i ? 0 : dy * H), duration: d, ease: "power4.inOut" }, t0);
    tl.fromTo(e.blur, { attr: { stdDeviation: "0 0" } }, { attr: { stdDeviation: amt }, duration: d / 2, ease: "power2.in" }, t0);
    tl.to(e.blur, { attr: { stdDeviation: "0 0" }, duration: d / 2, ease: "power2.out" }, c);
  },
  flash(tl, e, t0, c, d) {
    tl.fromTo(e.fx, { opacity: 0 }, { opacity: 1, duration: 0.07, ease: "power1.in" }, c - 0.07);
    tl.set(e.b, { opacity: 1 }, c);
    tl.to(e.fx, { opacity: 0, duration: d - 0.07, ease: "power2.out" }, c);
  },
  punch(tl, e, t0, c, d) {
    // hard cut with a zoom punch into the new shot
    tl.set(e.b, { opacity: 1 }, c);
    tl.fromTo(e.b, { scale: 1.18, filter: "blur(6px)" }, { scale: 1, filter: "blur(0px)", duration: d, ease: "expo.out" }, c);
  },
  flashcard(tl, e, t0, c, d) {
    // camera-flash style: two frames of pure white, then a hard cut to the end card
    const peak = c - 2 / 30;
    tl.fromTo(e.a, { filter: "brightness(1)" }, { filter: "brightness(2.4)", duration: peak - t0, ease: "power2.in" }, t0);
    tl.fromTo(e.fx, { opacity: 0 }, { opacity: 1, duration: peak - t0, ease: "power3.in" }, t0);
    tl.set("#card", { opacity: 1 }, c);
    tl.to(e.fx, { opacity: 0, duration: 0.12, ease: "power2.out" }, c);
  },
  tocard(tl, e, t0, c, d) {
    tl.fromTo(e.a, { scale: 1, filter: "blur(0px) brightness(1)" },
      { scale: 1.08, filter: "blur(22px) brightness(0.55)", duration: d, ease: "power2.inOut" }, t0);
    tl.fromTo("#card", { opacity: 0 }, { opacity: 1, duration: d * 0.8, ease: "power2.inOut" }, t0 + d * 0.2);
  },
};
