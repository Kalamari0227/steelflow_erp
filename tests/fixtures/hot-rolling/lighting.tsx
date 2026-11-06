import { useEffect } from 'react';
import { useThree } from '@react-three/fiber';
import { PMREMGenerator } from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

/** Original procedural studio illumination: no external environment or network asset. */
export function Studio() {
  const {gl,scene,invalidate}=useThree();
  useEffect(() => {
    const room=new RoomEnvironment(),generator=new PMREMGenerator(gl),target=generator.fromScene(room,.04),previous=scene.environment;
    scene.environment=target.texture;scene.environmentIntensity=.7;invalidate();
    return () => {scene.environment=previous;target.dispose();generator.dispose();room.dispose();};
  },[gl,scene,invalidate]);
  return null;
}
