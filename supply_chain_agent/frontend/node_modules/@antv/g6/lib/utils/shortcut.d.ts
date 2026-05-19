import EventEmitter from '@antv/event-emitter';
import { PinchHandler } from './pinch';
export interface ShortcutOptions {
}
export type ShortcutKey = string[];
type Handler = (event: any) => void;
export declare class Shortcut {
    private map;
    pinchHandler: PinchHandler | undefined;
    private boundHandlePinch;
    private emitter;
    private recordKey;
    constructor(emitter: EventEmitter);
    bind(key: ShortcutKey, handler: Handler): void;
    unbind(key: ShortcutKey, handler?: Handler): void;
    unbindAll(): void;
    /**
     * Check whether the given keys are being held down currently.
     * @param key - array of keys to check
     * @returns true if the given keys are being held down, false otherwise.
     */
    match(key: ShortcutKey): boolean;
    private bindEvents;
    private onKeyDown;
    private onKeyUp;
    private onKeyDownWindow;
    private onKeyUpWindow;
    private trigger;
    /**
     * <zh/> 扩展 wheel, drag 操作
     *
     * <en/> Extend wheel, drag operations
     * @param eventType - event name
     * @param event - event
     */
    private triggerExtendKey;
    private onWheel;
    private onDrag;
    private handlePinch;
    private onFocus;
    destroy(): void;
}
export {};
