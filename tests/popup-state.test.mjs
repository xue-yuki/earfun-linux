import test from 'node:test';
import assert from 'node:assert/strict';
import {ConnectionGate, popupBattery} from '../extension/earfun@ell.local/popup-state.js';
const ready = {connected: true, connection_checked: true, busy: false, updated_at: 100};

test('initial ready connection shows exactly once', () => {
    const gate = new ConnectionGate();
    assert.equal(gate.update(ready).show, true);
    assert.equal(gate.update({...ready, updated_at: 130}).show, false);
});
test('waits for a completed status instead of showing stale busy data', () => {
    const gate = new ConnectionGate();
    assert.equal(gate.update({...ready, busy: true}).show, false);
    assert.equal(gate.update(ready).show, true);
});
test('unknown initial connection does not rearm a reconnect', () => {
    const gate = new ConnectionGate(); gate.update(ready);
    gate.update({connected: false, connection_checked: false});
    assert.equal(gate.update(ready).show, false);
});
test('a real disconnect hides then reconnect shows once', () => {
    const gate = new ConnectionGate(); gate.update(ready);
    assert.equal(gate.update({connected: false}).hide, true);
    assert.equal(gate.update(ready).show, true);
    assert.equal(gate.update(ready).show, false);
});
test('null service state does not fabricate a disconnect', () => {
    const gate = new ConnectionGate(); gate.update(ready);
    assert.deepEqual(gate.update(null), {show: false, hide: false});
    assert.equal(gate.update(ready).show, false);
});
test('disconnect before initial status cancels pending popup', () => {
    const gate = new ConnectionGate(); gate.update({...ready, busy: true});
    gate.update({connected: false});
    assert.equal(gate.pending, false);
});
test('missing timestamp does not show an unchecked popup', () => {
    const gate = new ConnectionGate();
    assert.equal(gate.update({connected: true, busy: false}).show, false);
});
test('battery 0 and 100 are displayed, while unknown/invalid are not', () => {
    for (const value of [0, 50, 100]) {
        const state = {connected: true, values: {case: {data: {known: true, percent: value}}}};
        assert.equal(popupBattery(state, 'case'), value);
    }
    for (const value of [-1, 101, NaN, Infinity, '50', null]) {
        assert.equal(popupBattery({connected: true, values: {case: {data: {known: true, percent: value}}}}, 'case'), null);
    }
    assert.equal(popupBattery({connected: true, values: {case: {data: {known: false, percent: 50}}}}, 'case'), null);
});
test('left/right and case read separate live fields, never invented demo data', () => {
    const state = {connected: true, values: {earbuds: {data: {left: {known: true, percent: 70}, right: {known: true, percent: 65}}}, case: {data: {known: true, percent: 30}}}};
    assert.equal(popupBattery(state, 'left'), 70);
    assert.equal(popupBattery(state, 'right'), 65);
    assert.equal(popupBattery(state, 'case'), 30);
    assert.equal(popupBattery({...state, connected: false}, 'left'), null);
    assert.equal(popupBattery({connected: true}, 'case'), null);
});
