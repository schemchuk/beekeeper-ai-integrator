import { useEffect, useState } from "react";
import { cancelRender, continueRender, delayRender } from "remotion";
import { RIG, VIEWBOX } from "./rig";

export type Mouth = 0 | 1 | 2;

export type Pose = {
  mouth: Mouth; // 0 closed, 1 open, 2 wide
  eyesClosed: boolean;
  head: number; // head tilt, degrees
  arm: number; // arm-front swing, degrees
  wings: number; // wing flap, 1 = rest
};

// One fetch per SVG for the whole render; the markup is inserted as is, so the art stays the
// file in characters/ and a redraw needs no code change.
const cache = new Map<string, Promise<string>>();
const loadSvg = (url: string) => {
  if (!cache.has(url)) {
    cache.set(
      url,
      fetch(url).then((r) => {
        if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
        return r.text();
      }),
    );
  }
  return cache.get(url)!;
};

const useSvg = (url: string) => {
  const [markup, setMarkup] = useState<string | null>(null);
  const [handle] = useState(() => delayRender(`character ${url}`));
  useEffect(() => {
    loadSvg(url)
      .then((text) => {
        setMarkup(text);
        continueRender(handle);
      })
      .catch((err) => cancelRender(err));
  }, [url, handle]);
  return markup;
};

// Part switches and turns as CSS scoped to this instance: the SVG's own inline
// `display:none` is overridden with !important, transforms use viewBox coordinates.
const poseCss = (scope: string, name: string, pose: Pose) => {
  const rig = RIG[name];
  const part = (id: string) => `${scope} [id="${id}"]`;
  const visible = (id: string, on: boolean) =>
    `${part(id)}{display:${on ? "inline" : "none"} !important}`;
  const turn = (ids: string[], deg: number, [x, y]: [number, number]) =>
    `${ids.map(part).join(",")}{transform:rotate(${deg.toFixed(2)}deg);transform-origin:${x}px ${y}px}`;
  return [
    visible("mouth-closed", pose.mouth === 0),
    visible("mouth-open", pose.mouth === 1),
    visible("mouth-wide", pose.mouth === 2),
    visible("eyes-open", !pose.eyesClosed),
    visible("eyes-closed", pose.eyesClosed),
    turn(["head", "hat"], pose.head, rig.neck),
    turn(["arm-front"], pose.arm, rig.shoulder),
    `${part("wings")}{transform:scaleY(${pose.wings.toFixed(3)});transform-box:fill-box;transform-origin:center bottom}`,
  ].join("\n");
};

export const Character: React.FC<{
  name: string;
  instance: string; // unique per character on screen, scopes the CSS
  height: number; // px on the 1080x1920 canvas
  pose: Pose;
  style?: React.CSSProperties;
}> = ({ name, instance, height, pose, style }) => {
  const rig = RIG[name];
  const markup = useSvg(rig.svg);
  const scope = `[data-character="${instance}"]`;
  return (
    <div
      data-character={instance}
      style={{
        position: "absolute",
        height,
        width: (height * VIEWBOX.width) / VIEWBOX.height,
        ...style,
      }}
    >
      <style>{`${scope} svg{width:100%;height:100%;display:block}\n${poseCss(scope, name, pose)}`}</style>
      {markup ? (
        <div
          style={{ width: "100%", height: "100%" }}
          dangerouslySetInnerHTML={{ __html: markup }}
        />
      ) : null}
    </div>
  );
};

export const hasRig = (name: string | null): name is string =>
  name !== null && name in RIG;
