import { join } from 'node:path';
import { json } from './runtime.mjs';

export default class EvidenceReporter {
  assertions = [];
  tests = [];
  onStepEnd(test, result, step) {
    if (step.category === 'expect') this.assertions.push({ test: test.titlePath(), title: step.title, passed: !step.error, error: step.error?.message });
  }
  onTestEnd(test, result) {
    this.tests.push({ title: test.titlePath(), status: result.status, expectedStatus: test.expectedStatus, retry: result.retry, duration_ms: result.duration });
  }
  onEnd(result) {
    json(join(process.env.STEELFLOW_EVIDENCE_DIR, 'assertions.json'), { status: result.status, assertion_count: this.assertions.length, assertions: this.assertions, tests: this.tests });
  }
}
