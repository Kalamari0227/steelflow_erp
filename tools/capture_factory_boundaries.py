from pathlib import Path
import json
import sys
from importlib import import_module

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
c = import_module('app.operations.contracts')
service = import_module('app.operations.service')
advance_model = import_module('app.operations.engine').advance_model
build_fixture = import_module('app.operations.fixtures').build_fixture

TARGETS = {'CHARGE-A', 'BF-A', 'BOF-A', 'LF-A', 'CAST-SLAB', 'CUT-SLAB', 'CS-HR-02', 'CS-HR-03', 'HSM-A', 'CS-HR-05', 'CS-HR-06', 'CS-HR-07', 'CS-CR-02', 'CS-CR-03', 'CS-CR-04', 'CS-CR-09', 'CS-GA-02', 'CS-GA-05', 'CS-GA-06', 'CS-GA-10', 'FINAL-INSPECTION', 'PACKAGING', 'CS-PLATE-06'}


def view(model, material_id):
    lineage = model.materials[material_id].lineage_id
    members = {row.id for row in model.materials.values() if row.lineage_id == lineage}
    return {
        'run': model.run.model_dump(mode='json'),
        'materials': [row.model_dump(mode='json') for row in model.materials.values()],
        'processes': [row.model_dump(mode='json') for row in model.processes.values() if row.material_id in members],
        'transfers': [row.model_dump(mode='json') for row in model.transfers.values() if row.material_id in members],
        'lineage_edges': [row.model_dump(mode='json') for row in model.lineage_edges.values()],
        'shipments': [], 'shipment_materials': [],
    }


def main():
    model = advance_model(service._plan_model(build_fixture(), 'NORMAL'), c.Milliseconds(0), service.CALLBACKS).model
    sampled, records, splits = set(), [], []
    for _ in range(10000):
        running = [row for row in model.processes.values() if row.status == 'RUNNING' and row.end_ms is not None]
        deadlines = [row.end_ms for row in running]
        deadlines.extend(row.phase_end_ms for row in model.transfers.values() if row.phase_end_ms is not None and row.status not in ('WAITING', 'ARRIVED'))
        deadlines.extend(row.phase_end_ms for row in model.shipments.values() if row.phase_end_ms is not None and row.status != 'DELIVERED')
        future = [time for time in deadlines if time > model.run.elapsed_ms]
        target = min(future) if future else model.run.elapsed_ms + 100
        before = model
        model = advance_model(model, c.Milliseconds(target), service.CALLBACKS).model
        for process in running:
            if process.end_ms != target:
                continue
            material_id = process.material_id
            record = {'materialId': material_id, 'before': view(before, material_id), 'after': view(model, material_id)}
            if process.equipment_id in TARGETS and process.equipment_id not in sampled:
                records.append(record); sampled.add(process.equipment_id)
            if before.materials[material_id].active and not model.materials[material_id].active:
                splits.append(record)
        if TARGETS <= sampled and len(splits) >= 2:
            break
    else:
        raise RuntimeError(f'Boundary collection incomplete: {TARGETS - sampled}')
    destination = ROOT / 'src/operations/scene/fixtures'
    for name, rows in [('real-outfeed-boundaries.json', records), ('real-split-boundaries.json', splits)]:
        (destination / name).write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps({'source': 'actual backend engine with production callbacks', 'outfeed_boundaries': len(records), 'split_boundaries': len(splits), 'sampled_equipment': sorted(sampled)}))


if __name__ == '__main__':
    main()
