/**
 * 氛围层组件模板（Remotion / React）
 *
 * 设计约束：
 *   - 全是 frame 的纯函数 + 固定种子，逐帧可复现（禁 Math.random / Date.now）
 *   - 单层平均亮度 ≤ 0.05，四层叠加 ≤ 0.09
 *   - 运动周期 240–600f（8–20s），人眼只感知「活着」，不感知「在动」
 *   - 只做暖白/冷白，不引入第三种色相
 *
 * 用法：
 *   <Atmosphere frame={frame} intensity={1} />
 *   放在 Stage 之后、主体内容之前。纸字卡不要用（纸面有自己的材质）。
 *
 * 移植时替换：C / G / mulberry32 换成目标项目的设计令牌与随机函数。
 */
import React from "react";
import { AbsoluteFill } from "remotion";
import { C, G } from "./brand";          // 目标项目的颜色与画布尺寸令牌
import { mulberry32 } from "./motion";  // 确定性伪随机

const TAU = Math.PI * 2;

/** 斜向柔光带：一条 30° 的极宽渐变，缓慢横移 */
export const LightBand: React.FC<{ frame: number; speed?: number; opacity?: number }> = ({
  frame,
  speed = 1,
  opacity = 0.085,
}) => {
  const t = (frame * speed) / 520;
  const x = -30 + 30 * Math.sin(t * TAU);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity }}>
      <div
        style={{
          position: "absolute",
          left: `${x}%`,
          top: "-40%",
          width: "150%",
          height: "180%",
          transform: "rotate(-28deg)",
          background:
            "linear-gradient(90deg, rgba(240,235,225,0) 0%, rgba(240,235,225,0.55) 34%, rgba(240,235,225,0.85) 50%, rgba(240,235,225,0.55) 66%, rgba(240,235,225,0) 100%)",
          filter: "blur(60px)",
        }}
      />
    </AbsoluteFill>
  );
};

/** 扫描列：一道极淡的竖光带自左向右扫过，像扫描仪在读表 */
export const ScanColumn: React.FC<{ frame: number; period?: number; opacity?: number; width?: number }> = ({
  frame,
  period = 420,
  opacity = 0.07,
  width = 420,
}) => {
  const p = (frame % period) / period;
  const x = -width + p * (G.W + width * 2);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity }}>
      <div
        style={{
          position: "absolute",
          left: x,
          top: 0,
          width,
          height: G.H,
          background:
            "linear-gradient(90deg, rgba(240,235,225,0) 0%, rgba(240,235,225,0.5) 50%, rgba(240,235,225,0) 100%)",
          filter: "blur(18px)",
        }}
      />
    </AbsoluteFill>
  );
};

/** 半调网点：细密网点阵列，透明度缓慢呼吸。平色卡最缺的就是这层 */
export const Halftone: React.FC<{ frame: number; cell?: number; opacity?: number }> = ({
  frame,
  cell = 12,
  opacity = 0.075,
}) => {
  const breath = opacity * (0.62 + 0.38 * Math.sin((frame / 380) * TAU));
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: breath }}>
      <svg width={G.W} height={G.H}>
        <defs>
          <pattern id="atmo-halftone" width={cell} height={cell} patternUnits="userSpaceOnUse">
            <circle cx={cell / 2} cy={cell / 2} r={1.1} fill={C.text} />
          </pattern>
        </defs>
        <rect width={G.W} height={G.H} fill="url(#atmo-halftone)" />
      </svg>
    </AbsoluteFill>
  );
};

/** 数据雨：极暗的细刻度自上下落，像账目流水；种子固定 */
export const DataRain: React.FC<{ frame: number; count?: number; opacity?: number; seed?: number }> = ({
  frame,
  count = 40,
  opacity = 0.16,
  seed = 20261031,
}) => {
  const rand = mulberry32(seed);
  const cols = Array.from({ length: count }, () => ({
    x: rand() * G.W,
    speed: 0.4 + rand() * 1.1,
    len: 40 + rand() * 130,
    gap: 260 + rand() * 520,
    phase: rand() * 1200,
    w: rand() > 0.8 ? 2 : 1,
  }));
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity }}>
      <svg width={G.W} height={G.H}>
        {cols.map((c, i) => {
          const travel = (frame * c.speed + c.phase) % (G.H + c.gap);
          const y = travel - c.gap;
          const fade = Math.min(1, Math.min(travel, G.H + c.gap - travel) / 120);
          return (
            <rect key={i} x={c.x} y={y} width={c.w} height={c.len} fill={C.text}
              opacity={0.5 * Math.max(0, fade)} />
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};

/** 四角压暗 + 顶光，让氛围层不至于铺到边角抢字幕 */
export const EdgeFalloff: React.FC<{ strength?: number }> = ({ strength = 0.5 }) => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      background: `radial-gradient(118% 92% at 50% 42%, rgba(0,0,0,0) 44%, rgba(0,0,0,${strength}) 100%)`,
    }}
  />
);

/** 组合氛围层。intensity 0–1 逐镜调；纸字卡不要用 */
export const Atmosphere: React.FC<{ frame: number; intensity?: number; seed?: number }> = ({
  frame,
  intensity = 1,
  seed = 20261031,
}) => (
  <>
    <Halftone frame={frame} opacity={0.075 * intensity} />
    <LightBand frame={frame} opacity={0.085 * intensity} />
    <DataRain frame={frame} count={40} opacity={0.16 * intensity} seed={seed} />
    <ScanColumn frame={frame} opacity={0.07 * intensity} />
    <EdgeFalloff strength={0.5} />
  </>
);
