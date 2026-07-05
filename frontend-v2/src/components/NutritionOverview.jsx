import { useMemo } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { calcNutrition, generateAiSummary } from '../lib/nutrition';
import { useUiStore } from '../stores/uiStore';
import GlassCard from './GlassCard';

function AnimatedNumber({ value, className, reduce }) {
  return (
    <motion.span
      key={Math.round(value)}
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={reduce ? false : { opacity: 1, y: 0 }}
      transition={reduce ? {} : { duration: 0.3, ease: [0.32, 0.72, 0, 1] }}
      className={className}
    >
      {Math.round(value)}
    </motion.span>
  );
}

function ProgressBar({ label, value, target, unit, color, reduce }) {
  const ratio = target > 0 ? value / target : 0;
  const percent = Math.min(ratio * 100, 100);
  return (
    <div>
      <div className="flex justify-between items-baseline mb-1.5">
        <span className="text-xs text-[var(--text-secondary)]">{label}</span>
        <span className="font-number text-xs text-[var(--text-primary)]">
          <AnimatedNumber value={value} reduce={reduce} />
          <span className="text-[var(--text-tertiary)]"> / {target}{unit}</span>
        </span>
      </div>
      <div
        className="h-2 rounded-full overflow-hidden"
        style={{ background: 'var(--bg-tertiary)' }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={reduce ? false : { width: 0 }}
          animate={reduce ? { width: `${percent}%` } : { width: `${percent}%` }}
          transition={reduce ? {} : { duration: 0.8, ease: [0.32, 0.72, 0, 1] }}
        />
      </div>
    </div>
  );
}

function getCurrentMealSlot() {
  const h = new Date().getHours();
  if (h < 10) return 'breakfast';
  if (h < 14) return 'lunch';
  if (h < 20) return 'dinner';
  return 'snack';
}

export default function NutritionOverview({ meals, target }) {
  const nutrition = useMemo(() => calcNutrition(meals), [meals]);
  const summary = useMemo(() => generateAiSummary(meals, target), [meals, target]);
  const openSlidePanel = useUiStore(s => s.openSlidePanel);
  const reduce = useReducedMotion();

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 12 }}
      animate={reduce ? false : { opacity: 1, y: 0 }}
      transition={reduce ? {} : { duration: 0.4, ease: [0.32, 0.72, 0, 1] }}
    >
      <GlassCard strong>
        <div className="p-5">
          {/* 紧凑首屏：左侧大数字 + 右侧目标 / 副标题 */}
          <div className="flex items-baseline justify-center gap-1.5 mb-0.5">
            <AnimatedNumber
              value={nutrition.kcal}
              reduce={reduce}
              className="font-number text-4xl font-bold text-[var(--text-primary)] tracking-tight"
            />
            <span className="font-number text-lg text-[var(--text-tertiary)] font-medium">
              / {target.kcal}
            </span>
            <span className="text-xs text-[var(--text-tertiary)] ml-1">kcal</span>
          </div>
          <p className="text-center text-[11px] text-[var(--text-tertiary)] mb-4">
            今日摄入 / 每日目标
          </p>

          {/* 三条横向进度条 — 收紧间距 */}
          <div className="space-y-2.5 mb-3">
            <ProgressBar
              label="蛋白质"
              value={nutrition.protein}
              target={target.protein}
              unit="g"
              color="var(--nut-protein)"
              reduce={reduce}
            />
            <ProgressBar
              label="碳水化合物"
              value={nutrition.carb}
              target={target.carb}
              unit="g"
              color="var(--nut-carb)"
              reduce={reduce}
            />
            <ProgressBar
              label="脂肪"
              value={nutrition.fat}
              target={target.fat}
              unit="g"
              color="var(--nut-fat)"
              reduce={reduce}
            />
          </div>

          {/* 动态提示文案 — 品牌色软背景做记忆点 */}
          <div
            className="rounded-lg px-3 py-2 mb-3 text-xs leading-relaxed"
            style={{
              background: 'var(--brand-soft)',
              color: 'var(--brand-pressed)',
            }}
          >
            {summary}
          </div>

          {/* 通栏实心蓝主按钮 — 页面唯一强视觉主按钮 */}
          <button
            onClick={() => openSlidePanel(getCurrentMealSlot())}
            className="btn-primary w-full py-3 rounded-xl text-sm font-semibold"
          >
            快速添加今日餐食
          </button>
        </div>
      </GlassCard>
    </motion.div>
  );
}
