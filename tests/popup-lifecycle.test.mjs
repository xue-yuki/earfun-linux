// UI lifecycle contract tests with small mocks; these do not claim native Shell rendering.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

async function harness(enabled = true) {
    const timers = new Map(), chrome = new Set(), callbacks = new Map();
    let counter = 1;
    class Actor {
        constructor(props = {}) {Object.assign(this, props); this.children = []; this.opacity ??= 255; this.translation_y ??= 0; this.events = new Map();}
        add_child(child) {this.children.push(child);}
        set_position(x, y) {this.x = x; this.y = y;}
        set_clip(...clip) {this.clip = clip;}
        set_scale(x, y) {this.scale_x = x; this.scale_y = y;}
        set_pivot_point(...point) {this.pivot = point;}
        get clutter_text() {return {set_ellipsize() {}};}
        connect(name, callback) {this.events.set(name, callback); return counter++;}
        ease(params) {if (this.disposed) throw Error('Animation after destroy'); Object.assign(this, params); params.onComplete?.();}
        remove_all_transitions() {}
        destroy() {this.disposed = true;}
    }
    const signalHost = () => ({connect(name, callback) {const id = counter++; callbacks.set(id, callback);return id;},disconnect(id) {callbacks.delete(id);}});
    const Main = {
        layoutManager: {...signalHost(), primaryMonitor: {index: 0}, getWorkAreaForMonitor: () => ({x: 100, y: 50, width: 1920, height: 1080}),
            addChrome(actor) {chrome.add(actor);},removeChrome(actor) {chrome.delete(actor);}},
        sessionMode: {...signalHost(), currentMode: 'user', isLocked: false},
    };
    const GLib = {PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
        timeout_add(_priority, delay, callback) {const id = counter++;timers.set(id, {delay, callback});return id;},
        source_remove(id) {timers.delete(id);}};
    const St = {Widget: Actor, Label: Actor, Button: Actor, Settings: {get: () => ({enable_animations: enabled})}};
    const Clutter = {KEY_Escape: 27, EVENT_STOP: true, EVENT_PROPAGATE: false, AnimationMode: {EASE_OUT_CUBIC: 1, EASE_OUT_QUAD: 2}};
    const Gio = {File: {new_for_path: path => ({get_uri: () => 'file://' + path})}};
    const context = vm.createContext({console});
    const modules = {};
    for (const [name, value] of Object.entries({'gi://St': St, 'gi://GLib': GLib, 'gi://Clutter': Clutter, 'gi://Gio': Gio})) {
        modules[name] = new vm.SyntheticModule(['default'], function() {this.setExport('default', value);}, {context});
    }
    modules['resource:///org/gnome/shell/ui/main.js'] = new vm.SyntheticModule(['layoutManager', 'sessionMode'], function() {
        this.setExport('layoutManager', Main.layoutManager);this.setExport('sessionMode', Main.sessionMode);
    }, {context});
    modules['./popup-state.js'] = new vm.SourceTextModule(fs.readFileSync(new URL('../extension/earfun@ell.local/popup-state.js', import.meta.url), 'utf8'), {context});
    const module = new vm.SourceTextModule(fs.readFileSync(new URL('../extension/earfun@ell.local/popup.js', import.meta.url), 'utf8'), {context});
    await module.link(name => modules[name]);await module.evaluate();
    const state = {connected: true, name: 'ElamgaPods', values: {earbuds: {data: {left: {known: true, percent: 100}, right: {known: true, percent: 80}}}, case: {data: {known: true, percent: 50}}}};
    let opened = 0;
    const popup = new module.namespace.EarFunPopup({path: '/tmp/earfun'}, state, () => {opened++;});
    return {popup, timers, chrome, callbacks, Main, get opened() {return opened;}};
}

test('original animation schedules staggered earbuds and 5-second dismissal', async () => {
    const h = await harness();
    assert.deepEqual([...h.timers.values()].map(t => t.delay), [240, 700, 795, 1050, 1200, 5000]);
    assert.equal(h.popup._batteryLabels.case.text, '50%');
    assert.equal(h.popup._batteryLabels.right.text, '80%');
    assert.equal(h.chrome.size, 1);
    h.popup.destroy();
});
test('destroy removes all timers, chrome, signals; repeated destroy is safe', async () => {
    const h = await harness(); h.popup.destroy(); h.popup.destroy();
    assert.equal(h.timers.size, 0);assert.equal(h.chrome.size, 0);assert.equal(h.callbacks.size, 0);
    assert.equal(h.popup._actor.disposed, true);
});
test('reduced-motion uses final static pose and only the dismissal timer', async () => {
    const h = await harness(false);
    assert.equal(h.popup._actor.opacity, 255);assert.equal(h.popup._left.translation_y, -30);
    assert.deepEqual([...h.timers.values()].map(t => t.delay), [5000]);h.popup.destroy();
});
test('lock destroys popup and cancels pending animation', async () => {
    const h = await harness();h.Main.sessionMode.isLocked = true;
    [...h.callbacks.values()][1]();
    assert.equal(h.chrome.size, 0);assert.equal(h.timers.size, 0);
});
test('closing and opening controls cleans popup without stealing focus', async () => {
    const h = await harness();h.popup._footer.events.get('clicked')();
    assert.equal(h.opened, 1);assert.equal(h.timers.size, 0);assert.equal(h.chrome.size, 0);
});
test('popup stays in the top-right work-area corner after monitor changes', async () => {
    const h = await harness();
    assert.equal(h.popup._actor.x, 1656);assert.equal(h.popup._actor.y, 74);
    for (const area of [{x: 0, y: 0, width: 320, height: 600}, {x: -640, y: 50, width: 640, height: 400}]) {
        h.Main.layoutManager.getWorkAreaForMonitor = () => area;
        [...h.callbacks.values()][0]();
        const actor = h.popup._actor;
        assert.equal(actor.y, area.y + 24);
        assert(actor.x >= area.x);
        assert(Math.abs(area.x + area.width - (actor.x + 340 * actor.scale_x) - 24) <= 0.5);
        assert(actor.y + 430 * actor.scale_y <= area.y + area.height);
    }
    h.popup.destroy();
});
