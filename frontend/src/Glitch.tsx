import { useEffect, useRef } from "react";
import { Application, Container, Graphics, Text, TextStyle } from "pixi.js";

// pixi-glitch hero: RGB-split channel jitter + scanlines + sweep bar.
// Shared engine across every app (the console-terminal).
export function Glitch({ label }: { label: string }) {
  const hostRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let app: Application | null = null;
    let destroyed = false;
    const W = Math.max(320, host.clientWidth || 760);
    const H = 200;

    (async () => {
      const a = new Application();
      await a.init({
        width: W,
        height: H,
        background: "#000000",
        antialias: false,
        resolution: 1,
        autoDensity: false,
      });
      if (destroyed) {
        a.destroy(true);
        return;
      }
      app = a;
      host.appendChild(a.canvas);
      const stage = a.stage;

      const base = new TextStyle({
        fontFamily: "monospace",
        fontSize: W < 520 ? 40 : 60,
        fontWeight: "700",
        fill: "#f4f4f4",
        letterSpacing: 3,
      });
      const mk = (color: string) =>
        new TextStyle({
          fontFamily: "monospace",
          fontSize: W < 520 ? 40 : 60,
          fontWeight: "700",
          fill: color,
          letterSpacing: 3,
        });

      const group = new Container();
      const txt = label.toUpperCase();
      const tR = new Text({ text: txt, style: mk("#ff2b2b") });
      const tG = new Text({ text: txt, style: mk("#2bff88") });
      const tB = new Text({ text: txt, style: mk("#2b8bff") });
      const tW = new Text({ text: txt, style: base });
      [tR, tG, tB].forEach((t) => (t.blendMode = "add"));
      group.addChild(tR, tG, tB, tW);
      const cx = (W - tW.width) / 2;
      const cy = (H - tW.height) / 2 - 6;
      [tR, tG, tB, tW].forEach((t) => t.position.set(cx, cy));
      stage.addChild(group);

      // caret + prompt token under the title
      const sub = new Text({
        text: "> run status _",
        style: new TextStyle({
          fontFamily: "monospace",
          fontSize: 14,
          fill: "#7a7a7a",
          letterSpacing: 2,
        }),
      });
      sub.position.set(cx, cy + tW.height + 6);
      stage.addChild(sub);

      const scan = new Graphics();
      for (let y = 0; y < H; y += 3) {
        scan.rect(0, y, W, 1).fill({ color: 0xffffff, alpha: 0.045 });
      }
      stage.addChild(scan);

      const sweep = new Graphics();
      sweep.rect(0, 0, W, 26).fill({ color: 0xffffff, alpha: 0.06 });
      stage.addChild(sweep);

      let frame = 0;
      let sweepY = -40;
      const tick = () => {
        frame++;
        const burst = Math.random() < 0.08 ? 7 : 1.6;
        tR.position.set(cx + (Math.random() - 0.5) * 2 * burst, cy + (Math.random() - 0.5) * burst);
        tB.position.set(cx + (Math.random() - 0.5) * 2 * burst, cy + (Math.random() - 0.5) * burst);
        tG.position.set(cx + (Math.random() - 0.5) * burst, cy);
        group.alpha = Math.random() < 0.04 ? 0.55 : 1;
        sub.visible = Math.floor(frame / 24) % 2 === 0;
        sweepY += 1.4;
        if (sweepY > H) sweepY = -40;
        sweep.position.set(0, sweepY);
      };
      a.ticker.add(tick);
    })();

    return () => {
      destroyed = true;
      if (app) {
        app.destroy(true, { children: true });
        app = null;
      }
      if (host) host.innerHTML = "";
    };
  }, [label]);

  return <div className="glitch" ref={hostRef} />;
}
