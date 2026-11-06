import { describe, expect, it } from 'vitest';
import { parseMotionEnvelope } from './contracts';
import { fixture } from './testFixtures';

describe('actual JSON and UTF8 boundary', () => {
  it.each(['schema_version', 'revision', 'confirmed_sim_ms', 'phase_start_ms', 'phase_end_ms', 'effective_sim_ms'])('refuses float lexical spelling for integer %s', key => {
    // Given
    const raw = JSON.stringify(fixture().envelope).replace(new RegExp(`"${key}":(\\d+)`), `"${key}":$1.0`);
    // When
    const action = () => parseMotionEnvelope(raw);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
  });
  it.each(['true', '"1"', '1.0', '1e0'])('refuses schema literal coercion %s', token => {
    // Given
    const raw = JSON.stringify(fixture().envelope).replace('"schema_version":1', `"schema_version":${token}`);
    // When
    const action = () => parseMotionEnvelope(raw);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
  });
  it.each(['\ufeff', '\ufeff\ufeff', ' \ufeff'])('refuses invalid text BOM %j', prefix => {
    // Given
    const raw = prefix + JSON.stringify(fixture().envelope);
    // When
    const action = () => parseMotionEnvelope(raw);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'json' }));
  });
  it('accepts UTF8 bytes with one BOM and a multibyte execution identity', () => {
    // Given
    const input = fixture().envelope; input.execution_id = '실행-鋼-😀';
    const raw = new TextEncoder().encode('\ufeff' + JSON.stringify(input));
    // When
    const result = parseMotionEnvelope(raw);
    // Then
    expect(result.execution_id).toBe('실행-鋼-😀');
  });
  it.each([new Uint8Array([0xff, 0xfe, 0x7b, 0]), new Uint8Array([0xc0, 0xaf]), new Uint8Array([0xed, 0xa0, 0x80])])('refuses malformed UTF8 bytes %j', raw => {
    // Given / When
    const action = () => parseMotionEnvelope(raw);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'json' }));
  });
});
