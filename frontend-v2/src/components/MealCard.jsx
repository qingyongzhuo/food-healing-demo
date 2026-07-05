import { motion, useReducedMotion } from 'framer-motion';
import { Plus } from '@phosphor-icons/react';
import { useMealStore } from '../stores/mealStore';
import { useUiStore } from '../stores/uiStore';
import { calcNutrition } from '../lib/nutrition';
import FoodTag from './FoodTag';
import GlassCard from './GlassCard';

export default function MealCard({ slot }) {
  const meals = useMealStore(s => s.meals);
  const removeFood = useMealStore(s => s.removeFood);
  const openSlidePanel = useUiStore(s => s.openSlidePanel);
  const reduce = useReducedMotion();
  const foods = meals[slot.key] || [];
  const mealNutrition = calcNutrition({ [slot.key]: foods });
  const hasFoods = foods.length > 0;

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 12 }}
      animate={reduce ? false : { opacity: 1, y: 0 }}
      transition={reduce ? {} : { duration: 0.4, ease: [0.32, 0.72, 0, 1] }}
    >
      <GlassCard>
        <div className="p-5">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-base leading-none">{slot.emoji}</span>
              <div>
                <h3 className="text-sm font-semibold text-[var(--text-primary)] leading-tight">
                  {slot.label}
                </h3>
                <p className="text-[10px] text-[var(--text-tertiary)] leading-tight mt-0.5">
                  {slot.timeLabel}
                </p>
              </div>
            </div>
            <button
              onClick={() => openSlidePanel(slot.key)}
              className="text-xs font-medium transition-colors active:scale-95"
              style={{ color: 'var(--accent)' }}
              aria-label={`添加${slot.label}`}
            >
              + 添加食物
            </button>
          </div>

          {/* Foods */}
          {hasFoods ? (
            <>
              <div className="flex flex-wrap gap-1.5 mb-2.5">
                {foods.map(food => (
                  <FoodTag
                    key={food._id}
                    food={food}
                    onRemove={(id) => removeFood(slot.key, id)}
                  />
                ))}
              </div>
              {/* Nutrition summary */}
              <div
                className="flex items-center gap-3 text-[10px] text-[var(--text-tertiary)] pt-2.5 font-number"
                style={{ borderTop: '1px solid var(--divider)' }}
              >
                <span>{Math.round(mealNutrition.kcal)} kcal</span>
                <span>蛋白 {Math.round(mealNutrition.protein)}g</span>
                <span>碳水 {Math.round(mealNutrition.carb)}g</span>
                <span>脂肪 {Math.round(mealNutrition.fat)}g</span>
              </div>
            </>
          ) : (
            <button
              onClick={() => openSlidePanel(slot.key)}
              className="w-full py-3 rounded-xl text-xs text-[var(--text-tertiary)] transition-colors active:scale-[0.98] flex items-center justify-center gap-1.5"
              style={{
                border: '1px dashed var(--border-color)',
                background: 'var(--bg-secondary)',
              }}
            >
              <Plus size={12} />
              暂无{slot.label}饮食记录，点击添加
            </button>
          )}
        </div>
      </GlassCard>
    </motion.div>
  );
}
