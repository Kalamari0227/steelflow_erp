import { Block, Coil, Cylinder, Label, MaterialShape, palette, Rollers, steel } from './parts';

function Gantry({ x = 0, height = 3.5 }: { x?: number; height?: number }) {
  return <group>
    {[-1.4, 1.4].map((z) => <Block key={z} position={[x, height / 2, z]} size={[0.18, height, 0.18]} color={palette.orange} />)}
    <Block position={[x, height, 0]} size={[0.35, 0.28, 3.3]} color={palette.orange} />
    <Block position={[x, height - 0.65, 0]} size={[0.05, 1.2, 0.05]} color={palette.rail} />
  </group>;
}

export function Equipment({ stageId, zone, detailed = false }: { stageId: string; zone: number; detailed?: boolean }) {
  if (stageId === 'ironmaking') {
    if (zone === 0) return <group>
      {[0, 0.9].map((z) => <Cylinder key={z} position={[0, 1.3, z - 0.45]} radius={0.42} top={0.3} height={2.5} color={steel} />)}
      <Block position={[0.2, 1.25, 0]} size={[2.8, 0.2, 0.5]} rotation={[0, 0, 0.6]} color={palette.rail} />
    </group>;
    if (zone === 1) return <group>
      <Cylinder position={[0, 1.5, 0]} radius={0.9} top={0.6} height={2.8} />
      <Cylinder position={[0, 3.2, 0]} radius={0.6} top={0.25} height={0.8} color={palette.rail} />
      <Cylinder position={[0, 3.85, 0]} radius={0.18} height={0.6} color={palette.rail} />
      {[0.8, 1.6, 2.4].map((y) => <Cylinder key={y} position={[0, y, 0]} radius={0.98 - y * 0.1} height={0.1} color={palette.orange} />)}
      <Block position={[0.8, 0.4, 0]} size={[1.8, 0.13, 0.25]} color={palette.orange} />
    </group>;
    return <group><MaterialShape form="molten" position={[0, 0.9, 0]} /><Gantry />
      <Block position={[0, 0.2, 0]} size={[1.8, 0.25, 1.5]} color={palette.rail} /></group>;
  }
  if (stageId === 'steelmaking') {
    if (zone === 0) return <group><MaterialShape form="molten" position={[0, 1, 0]} /><Gantry /></group>;
    if (zone === 1) return <group>
      <Cylinder position={[0, 1.5, 0]} radius={0.75} top={0.95} height={1.8} color={steel} rotation={[0, 0, -0.2]} />
      <Cylinder position={[0.18, 2.38, 0]} radius={0.7} height={0.05} color={palette.orange} />
      <Cylinder position={[0, 3.2, 0]} radius={0.08} height={1.7} color={palette.rail} />
      {[-1.1, 1.1].map((z) => <Block key={z} position={[0, 1.1, z]} size={[0.5, 2, 0.3]} color={palette.rail} />)}
    </group>;
    return <group><Cylinder position={[0, 0.8, 0]} radius={0.8} height={1.4} />
      {[-0.4, 0, 0.4].map((x) => <Cylinder key={x} position={[x, 2.1, 0]} radius={0.07} height={1.4} color={palette.rail} />)}
      <Block position={[0, 2.85, 0]} size={[1.8, 0.3, 1.3]} color={palette.orange} /></group>;
  }
  if (stageId === 'casting') {
    if (zone === 0) return <group><Gantry height={3.7} /><MaterialShape form="molten" position={[0, 2.6, 0]} />
      <Block position={[0, 1.7, 0]} size={[1.8, 0.45, 2.5]} color={palette.rail} /></group>;
    if (zone === 1) return <group>{[-0.85, 0, 0.85].map((z, i) => <group key={z}>
      <Block position={[-0.6, 1.25, z]} size={[0.26, 2, i === 0 ? 0.65 : 0.25]} color={palette.orange} />
      <Block position={[0, 0.7, z]} size={[1.4, 0.2, i === 0 ? 0.65 : 0.25]} color={palette.orange} />
      <Rollers x={-0.5} z={z} count={4} width={0.7} />
    </group>)}</group>;
    return <group>{['SLAB', 'BLOOM', 'BILLET'].map((form, i) => <group key={form}>
      <MaterialShape form={form} position={[0, 0.5, (i - 1) * 0.95]} hot />
      {detailed && <Label text={form} position={[0, 1.4, (i - 1) * 0.95]} width={1.5} />}
    </group>)}</group>;
  }
  if (stageId === 'hot_rolling' || stageId === 'cold_rolling') {
    const hot = stageId === 'hot_rolling';
    if (zone === 0) return hot ? <group>
      <Block position={[0, 0.9, 0]} size={[2, 1.6, 2.2]} color={palette.roof} />
      <Block position={[1.02, 0.65, 0]} size={[0.05, 0.55, 1.5]} color={palette.orange} />
      <Cylinder position={[-0.6, 2.1, -0.6]} radius={0.15} height={1} color={palette.rail} />
    </group> : <Coil position={[0, 0.85, 0]} />;
    if (zone === 1) return <group>
      <Rollers x={-1.1} count={6} />
      <Block position={[0, 0.8, 0]} size={[3, 0.06, 1.15]} color={hot ? palette.orange : '#b2c4cc'} />
      {[-0.7, 0.7].map((x) => <group key={x}>
        {[-1, 1].map((z) => <Block key={z} position={[x, 1.1, z]} size={[0.35, 2, 0.35]} color={steel} />)}
        <Cylinder position={[x, 1.15, 0]} radius={0.3} height={1.8} rotation={[Math.PI / 2, 0, 0]} color={palette.rail} />
        <Block position={[x, 2.1, 0]} size={[0.5, 0.25, 2.3]} color={palette.orange} />
      </group>)}
    </group>;
    return <group><Coil position={[0.4, 0.85, 0]} color={hot ? '#b7795e' : steel} />
      <Block position={[-0.7, 0.9, 0]} size={[1.3, 0.04, 1]} color={hot ? palette.orange : '#b2c4cc'} /></group>;
  }
  if (stageId === 'coating') {
    if (zone === 0) return <group><Coil position={[-0.4, 0.85, 0]} />
      <Block position={[0.5, 1.5, 0]} size={[0.65, 2.8, 1.5]} color={palette.roof} />
      <Block position={[0.7, 1.6, 0]} size={[0.06, 2.6, 0.8]} color={steel} /></group>;
    if (zone === 1) return <group>
      <Block position={[0, 0.6, 0]} size={[2.2, 0.95, 2.1]} color={palette.rail} />
      <Block position={[0, 1.09, 0]} size={[1.9, 0.05, 1.8]} color="#a9cbc6" />
      <Block position={[0.25, 2, 0]} size={[0.06, 2.4, 0.9]} color="#b2c4cc" />
      <Cylinder position={[0.25, 3.2, 0]} radius={0.2} height={1.3} rotation={[Math.PI / 2, 0, 0]} />
      {detailed && <Label text="GI · GA · HGI 용융욕" position={[0, 3.7, 0]} width={2.7} />}
    </group>;
    return <group>
      {[-0.6, 0.1, 0.8].map((x) => <group key={x}>
        <Block position={[x, 0.65, 0]} size={[0.55, 1.1, 1.8]} color={steel} />
        <Block position={[x, 1.25, 0]} size={[0.12, 0.15, 1.3]} color={palette.orange} />
      </group>)}
      <Block position={[0, 1.08, 0]} size={[2.4, 0.05, 0.9]} color="#d4dfe5" />
      {detailed && <Label text="EG · 전해 도금 셀" position={[0, 2.3, 0]} width={2.8} />}
    </group>;
  }
  if (stageId === 'finishing') {
    if (zone === 0) return <group><Rollers x={-1.1} count={6} /><Gantry height={2.5} />
      <Block position={[0, 0.85, 0]} size={[2.9, 0.08, 1.25]} color={steel} />
      <Block position={[0, 1.9, 0]} size={[0.5, 0.25, 0.45]} color={palette.teal} /></group>;
    if (zone === 1) return <group><Coil position={[0, 0.9, 0]} /><Gantry height={2.8} />
      <Block position={[0.5, 0.9, 0]} size={[0.1, 1.5, 1.5]} color={palette.orange} /></group>;
    return <group>{[-0.65, 0.65].map((z) => <Coil key={z} position={[0, 0.9, z]} color="#a5b6c1" />)}
      <Block position={[0, 0.1, 0]} size={[2.3, 0.15, 2.8]} color="#bdab8f" /></group>;
  }
  return <group>
    {zone === 0 ? [-0.65, 0.65].map((z) => <Coil key={z} position={[0, 0.85, z]} />)
      : [0, 1, 2].map((i) => <MaterialShape key={i} form={zone === 1 ? 'SLAB' : i === 0 ? 'BLOOM' : 'BILLET'}
        position={[0, 0.3 + i * 0.3, 0]} />)}
    <Block position={[0, 0.1, 0]} size={[2.1, 0.15, 2.5]} color="#bdab8f" />
    {zone === 1 && <Gantry height={3.5} />}
  </group>;
}
