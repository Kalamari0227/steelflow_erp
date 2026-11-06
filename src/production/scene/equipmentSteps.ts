type StepDescriptor = { readonly name: string; readonly equipment_id: string };
type Association = { readonly equipment: readonly string[]; readonly name?: string };

// Only geometry that represents a named process asset can select that asset's step.
// Material stands, transfer ladles and output coils have no process-step association.
const associations: Record<string, readonly (Association | null)[]> = {
  ironmaking: [
    { equipment: ['BF-01'], name: '원료 장입' },
    { equipment: ['BF-01'], name: '고로 환원·출선' },
    null,
  ],
  steelmaking: [null, { equipment: ['BOF-01'] }, { equipment: ['LF-01'] }],
  casting: [null, { equipment: ['CASTER-SLAB', 'CASTER-BLOOM', 'CASTER-BILLET'] }, null],
  hot_rolling: [{ equipment: ['REHEAT-01'] }, { equipment: ['HSM-A', 'HSM-B'] }, null],
  cold_rolling: [null, { equipment: ['CRM-01'] }, null],
  coating: [{ equipment: ['HGI-PICKLE-01'] }, { equipment: ['HDG-01'] }, { equipment: ['EGL-01'] }],
  finishing: [{ equipment: ['QC-01'] }, { equipment: ['PACK-01'] }, null],
  stock: [0, 1, 2].map(() => ({ equipment: ['PRODUCTION-STOCK'] })),
};

export function equipmentStepIndex(stageId: string, zone: number, steps: readonly StepDescriptor[]): number {
  const association = associations[stageId]?.[zone];
  if (!association) return -1;
  return steps.findIndex((step) => association.equipment.includes(step.equipment_id)
    && (!association.name || step.name === association.name));
}
