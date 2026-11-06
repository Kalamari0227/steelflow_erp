import {readFileSync} from 'node:fs';
import {factorySnapshotSchema} from '../../../src/operations/contractsV3';
import {parseMotionContext,parseMotionEnvelopeValue,evaluateMotion} from '../../../src/operations/scene/motion/contracts';
import {recipes} from '../../../src/operations/scene/motion/testFixtures';
import {z} from 'zod';
const input=z.object({envelope:z.unknown(),context:z.object({snapshot:z.unknown()}).passthrough()}).parse(JSON.parse(readFileSync(process.argv[2]??'', 'utf8'))),snapshot=factorySnapshotSchema.safeParse(input.context.snapshot);
if(!snapshot.success){console.error(JSON.stringify(snapshot.error.issues,null,2));process.exitCode=2;}else{try{console.log(JSON.stringify(evaluateMotion(parseMotionEnvelopeValue(input.envelope),parseMotionContext(input.context),recipes)));}catch(e){console.error(e);process.exitCode=2;}}
