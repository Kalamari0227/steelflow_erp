import { useEffect, useMemo, useRef } from 'react';
import { CanvasTexture } from 'three';
import type { Sprite } from 'three';
import { useFrame } from '@react-three/fiber';
import type { Point } from './layout';

export function SceneLabel({ text, at, active = false }: { readonly text: string; readonly at: Point; readonly active?: boolean }) {
  const sprite = useRef<Sprite>(null);
  const label = useMemo(() => {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    const font = `${active ? 600 : 500} ${active ? 30 : 26}px -apple-system, sans-serif`;
    if (context) context.font = font;
    canvas.width = Math.ceil(context?.measureText(text).width ?? text.length * 28) + 24;
    canvas.height = 48;
    if (context) {
      context.font = font; context.textAlign = 'center'; context.textBaseline = 'middle';
      context.lineWidth = 5;
      context.strokeStyle = 'rgba(248,250,247,0.92)';
      context.strokeText(text, canvas.width / 2, 24);
      context.fillStyle = active ? '#0c6474' : '#233e48';
      context.fillText(text, canvas.width / 2, 24);
    }
    return { texture: new CanvasTexture(canvas), width: canvas.width / 2, height: canvas.height / 2 };
  }, [text, active]);
  useEffect(() => () => label.texture.dispose(), [label]);
  useFrame(({ camera }) => { sprite.current?.scale.set(label.width / camera.zoom, label.height / camera.zoom, 1); });
  return <sprite ref={sprite} position={[...at]} raycast={() => null}><spriteMaterial map={label.texture} transparent depthTest={false} depthWrite={false} /></sprite>;
}
