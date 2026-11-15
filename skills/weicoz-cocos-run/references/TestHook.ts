// 标准测试钩子模板。复制到工程 assets/scripts/game/TestHook.ts，不改本文件的接口名，只实现 TestHookAdapter。
// 主控组件 start() 里调用：installTestHook({ ... })。仅 DEBUG（debug 构建与预览）生效，release 构建自动剔除。
// 试玩脚本只通过 globalThis.__game 读写，字段名固定，供 weicoz-cocos-run 的通用脚本直接使用。
import { DEBUG } from 'cc/env';

/** 屏幕比例坐标：0～1，左上为原点。脚本乘以视口宽高后真实点击。 */
export interface Frac { fx: number; fy: number }

export interface TestHookAdapter {
    /** 当前规则状态。至少含 status（如 'playing' | 'won' | 'lost'）；关卡制游戏含 levelIndex、levelCount。 */
    state(): { status: string; [k: string]: unknown };
    /** 当前界面名，如 'home' | 'game' | 'levels'。 */
    screen(): string;
    /** 没有进行中的动画、可以接受输入时为 true。 */
    idle(): boolean;
    /** 结算或过关面板已显示且按钮可点时为 true。 */
    panelOpen(): boolean;
    /** 按名字返回可点击按钮的位置，如 'start'、'next'、'restart'；没有该按钮返回 null。 */
    button(name: string): Frac | null;
    /** 下一步正确操作的位置（如提示的那根箭头）；没有时返回 null。 */
    hint(): Frac | null;
    /** 一个会出错的操作位置（如被挡的箭头），用于验证扣命反馈；没有时返回 null。 */
    wrong?(): Frac | null;
    /** 本该清空却仍可见的元素数（如通关后剩下的遮盖块）。视觉巡检发现的残留问题都在这里计数。 */
    residue?(): number;
    /** 快速模式：true 时动画时长乘 0.1，用于日常全量回归。 */
    fast?(on: boolean): void;
    /** 清空存档，让脚本可重跑。 */
    resetSave?(): void;
}

/** 体验指标：游戏在对应时机调用 recordMetric，脚本用 __game.metrics() 读取。 */
interface LevelMetric { level: unknown; ms: number; taps: number; misses: number }
const metrics = { taps: 0, misses: 0, levels: [] as LevelMetric[], levelStart: 0, levelTaps: 0, levelMisses: 0 };

/** 'start' 关卡开始；'tap' 一次有效操作；'miss' 一次出错操作；'win' 通关。 */
export function recordMetric(kind: 'start' | 'tap' | 'miss' | 'win', level?: unknown): void {
    if (!DEBUG) return;
    const now = Date.now();
    if (kind === 'start') { metrics.levelStart = now; metrics.levelTaps = 0; metrics.levelMisses = 0; }
    if (kind === 'tap') { metrics.taps++; metrics.levelTaps++; }
    if (kind === 'miss') { metrics.misses++; metrics.levelMisses++; }
    if (kind === 'win') metrics.levels.push({ level, ms: now - metrics.levelStart, taps: metrics.levelTaps, misses: metrics.levelMisses });
}

export function installTestHook(a: TestHookAdapter): void {
    if (!DEBUG) return;
    (globalThis as any).__game = {
        state: () => a.state(),
        screen: () => a.screen(),
        idle: () => a.idle(),
        panelOpen: () => a.panelOpen(),
        button: (name: string) => a.button(name),
        hint: () => a.hint(),
        wrong: () => a.wrong?.() ?? null,
        residue: () => a.residue?.() ?? 0,
        fast: (on: boolean) => a.fast?.(on),
        resetSave: () => a.resetSave?.(),
        metrics: () => ({ taps: metrics.taps, misses: metrics.misses, levels: metrics.levels.slice() }),
    };
}
