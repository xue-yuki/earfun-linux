import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {popupBattery} from './popup-state.js';

// Geometry and timing follow the original approved preview.
// PNGs are byte-identical to the first generated layers, not the later poses.
export class EarFunPopup {
    constructor(extension, state, openControls) {
        this._timers = new Set();
        this._destroyed = false;
        this._added = false;
        this._actor = new St.Widget({
            style_class: 'popup-menu-content earfun-welcome',
            width: 340, height: 430, reactive: true,
            accessible_name: 'EarFun tersambung',
        });
        this._actor.opacity = 0;
        this._actor.translation_y = 26;
        try {
            const title = new St.Label({style_class: 'earfun-welcome-title', width: 270});
            title.set_position(35, 27);
            title.clutter_text.set_ellipsize(3);
            this._actor.add_child(title);
            this._title = title;
            const status = new St.Label({text: 'Tersambung', style_class: 'earfun-welcome-status', width: 280});
            status.set_position(30, 57);
            this._actor.add_child(status);
            const close = new St.Button({style_class: 'earfun-welcome-close', label: '×',
                width: 36, height: 36, can_focus: true, accessible_name: 'Tutup popup EarFun'});
            close.set_position(294, 8);
            close.connect('clicked', () => this.close());
            this._actor.add_child(close);
            const scene = new St.Widget({width: 260, height: 240});
            scene.set_position(40, 99);
            this._actor.add_child(scene);
            this._lid = this._sprite(extension, scene, 'case-lid.png', 19, -23, 222, 92, -50.2, -25.8, 323);
            this._body = this._sprite(extension, scene, 'case-body.png', 24, 63, 212, 163, -55.4, -112.2, 323);
            this._left = this._sprite(extension, scene, 'earbud-left.png', 58, 89, 67, 90, -37, -30.8, 150.8);
            this._right = this._sprite(extension, scene, 'earbud-right.png', 135, 89, 67, 90, -47.5, -31.3, 150.8);
            this._batteryRow = new St.Widget({width: 288, height: 62});
            this._batteryRow.set_position(26, 331);
            this._actor.add_child(this._batteryRow);
            this._batteryLabels = {};
            this._batteryBars = {};
            for (const [index, [key, label]] of [['left', 'Kiri'], ['case', 'Casing'], ['right', 'Kanan']].entries()) {
                const column = new St.Widget({width: 96, height: 62});
                column.set_position(index * 96, 0);
                const heading = new St.Label({text: label, width: 96, style_class: 'earfun-welcome-battery-label'});
                const value = new St.Label({text: '—', width: 96, style_class: 'earfun-welcome-battery-value'});
                value.set_position(0, 18);
                const track = new St.Widget({width: 54, height: 4, style_class: 'earfun-welcome-track'});
                track.set_position(21, 52);
                const bar = new St.Widget({width: 0, height: 4, style_class: 'earfun-welcome-bar'});
                track.add_child(bar);
                column.add_child(heading);
                column.add_child(value);
                column.add_child(track);
                this._batteryLabels[key] = value;
                this._batteryBars[key] = bar;
                this._batteryRow.add_child(column);
            }
            const footer = new St.Button({label: 'EarFun Air Pro 4i · Kontrol', width: 288, height: 30,
                style_class: 'earfun-welcome-footer', can_focus: true});
            footer.set_position(26, 395);
            footer.connect('clicked', () => {this.close(); openControls();});
            this._actor.add_child(footer);
            this._footer = footer;
            this._actor.connect('key-press-event', (_actor, event) => {
                if (event.get_key_symbol() === Clutter.KEY_Escape) {
                    this.close();
                    return Clutter.EVENT_STOP;
                }
                return Clutter.EVENT_PROPAGATE;
            });
            this._monitorId = Main.layoutManager.connect('monitors-changed', () => this._place());
            this._sessionId = Main.sessionMode.connect('updated', () => {
                if (Main.sessionMode.isLocked || Main.sessionMode.currentMode !== 'user')
                    this.destroy();
            });
            this.update(state);
            Main.layoutManager.addChrome(this._actor, {affectsStruts: false, trackFullscreen: true});
            this._added = true;
            this._place();
            this._animate();
        } catch (error) {
            this.destroy();
            throw error;
        }
    }

    _sprite(extension, scene, filename, x, y, width, height, imageX, imageY, imageWidth) {
        const frame = new St.Widget({width, height});
        frame.set_position(x, y);
        frame.set_clip(0, 0, width, height);
        const uri = Gio.File.new_for_path(`${extension.path}/assets/${filename}`).get_uri();
        const image = new St.Widget({width: imageWidth, height: imageWidth * 1199 / 1312,
            style: `background-image: url("${uri}"); background-size: contain; background-repeat: no-repeat;`});
        image.set_position(imageX, imageY);
        frame.add_child(image);
        scene.add_child(frame);
        return frame;
    }

    _place() {
        if (this._destroyed)
            return;
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor) {
            this.destroy();
            return;
        }
        const area = Main.layoutManager.getWorkAreaForMonitor(monitor.index);
        const scale = Math.min(1, Math.max(0.4, (area.width - 24) / 340), Math.max(0.4, (area.height - 32) / 430));
        this._actor.set_scale(scale, scale);
        this._actor.set_position(Math.round(area.x + area.width - 340 * scale - 24), Math.round(area.y + 24));
    }

    _later(delay, callback) {
        const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, delay, () => {
            this._timers.delete(id);
            if (!this._destroyed)
                callback();
            return GLib.SOURCE_REMOVE;
        });
        this._timers.add(id);
    }

    _animate() {
        const enabled = St.Settings.get().enable_animations;
        if (!enabled) {
            this._actor.opacity = 255;
            this._actor.translation_y = 0;
            this._left.translation_y = this._right.translation_y = -30;
        } else {
            this._actor.ease({opacity: 255, translation_y: 0, duration: 430, mode: Clutter.AnimationMode.EASE_OUT_CUBIC});
            this._lid.set_pivot_point(0.5, 0.98);
            this._lid.scale_y = 0.08;
            this._lid.opacity = 0;
            this._batteryRow.opacity = this._footer.opacity = 0;
            this._later(240, () => this._lid.ease({scale_y: 1, opacity: 255, duration: 650, mode: Clutter.AnimationMode.EASE_OUT_CUBIC}));
            for (const [index, earbud] of [this._left, this._right].entries()) {
                this._later(700 + index * 95, () => earbud.ease({translation_y: -35, duration: 525,
                    mode: Clutter.AnimationMode.EASE_OUT_CUBIC,
                    onComplete: () => {
                        if (!this._destroyed)
                            earbud.ease({translation_y: -30, duration: 175, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
                    }}));
            }
            this._batteryRow.translation_y = 6;
            this._later(1050, () => this._batteryRow.ease({opacity: 255, translation_y: 0, duration: 350, mode: Clutter.AnimationMode.EASE_OUT_QUAD}));
            this._later(1200, () => this._footer.ease({opacity: 255, duration: 300}));
        }
        this._later(5000, () => this.close());
    }

    update(state) {
        if (this._destroyed)
            return;
        this._title.text = state?.name ?? 'EarFun Air Pro 4i';
        for (const key of ['left', 'case', 'right']) {
            const value = popupBattery(state, key);
            this._batteryLabels[key].text = value === null ? '—' : `${value}%`;
            this._batteryBars[key].width = value === null ? 0 : 54 * value / 100;
        }
    }

    close() {
        if (this._destroyed || this._closing)
            return;
        this._closing = true;
        for (const id of this._timers)
            GLib.source_remove(id);
        this._timers.clear();
        this._actor.remove_all_transitions();
        if (St.Settings.get().enable_animations)
            this._actor.ease({opacity: 0, translation_y: 14, duration: 350, onComplete: () => this.destroy()});
        else
            this.destroy();
    }

    destroy() {
        if (this._destroyed)
            return;
        this._destroyed = true;
        for (const id of this._timers)
            GLib.source_remove(id);
        this._timers.clear();
        if (this._monitorId)
            Main.layoutManager.disconnect(this._monitorId);
        if (this._sessionId)
            Main.sessionMode.disconnect(this._sessionId);
        if (this._added)
            Main.layoutManager.removeChrome(this._actor);
        this._actor.destroy();
    }
}
