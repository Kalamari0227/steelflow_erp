import type { MaterialSupport } from './shapes';
export const FORM_FAMILIES = {
  ORE: ['ORE'], HOT_METAL: ['LIQUID_IRON'], LIQUID_STEEL: ['LIQUID_STEEL'], SCRAP: ['SCRAP'],
  SLAB: ['SLAB'], BLOOM: ['BLOOM'], BILLET: ['BILLET'], HOT_SLAB: ['SLAB'], HOT_BLOOM: ['BLOOM'], HOT_BILLET: ['BILLET'],
  HOT_STRIP: ['STRIP'], HOT_PLATE: ['PLATE'], STRIP: ['STRIP'], THIN_STRIP: ['STRIP'], COATED_STRIP: ['STRIP'],
  HR_COIL: ['COIL'], CR_COIL: ['COIL'], GI_COIL: ['COIL'], GA_COIL: ['COIL'], HGI_COIL: ['COIL'], EG_COIL: ['COIL'],
  GO_COIL: ['COIL'], NGO_COIL: ['COIL'], WIRE: ['WIRE_COIL'], WIRE_COIL: ['WIRE_COIL'], PLATE: ['PLATE'],
  STS_HR_COIL: ['COIL'], STS_CR_COIL: ['COIL'], STS_PLATE: ['PLATE'], TI_INGOT: ['INGOT'], TI_SLAB: ['SLAB'],
  TI_HR_COIL: ['COIL'], TI_CR_COIL: ['COIL'], TI_SHEET: ['PLATE'], TI_PLATE: ['PLATE'], COKE: ['ORE'],
  COAL: ['ORE'], LIMESTONE: ['ORE'], ALLOY: ['ORE'], SLAG: ['ORE'], BYPRODUCT: ['ORE'],
} as const satisfies Record<MaterialSupport['form'], readonly string[]>;
