import { z } from 'zod';
import rawCampus from '../../../shared/factory-campus.json';

const Point = z.tuple([z.number().finite(), z.number().finite(), z.number().finite()]);
const Area = z.object({ center: Point, size: Point });
export const factoryCampus = z.object({
  version: z.literal(1), land: Area, water: Area,
  halls: z.array(z.object({
    id: z.string(), stage_id: z.string(), center: Point, size: Point, rotation: z.number(),
    kind: z.enum(['hot', 'rolling', 'finishing', 'specialty', 'warehouse', 'yard']),
  })),
  roads: z.array(z.object({ id: z.string(), points: z.array(Point), width: z.number().positive() })),
  districts: z.array(z.object({ id: z.string(), label: z.string(), position: Point })),
}).parse(rawCampus);
