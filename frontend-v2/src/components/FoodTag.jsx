import { useState, useRef } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { X } from '@phosphor-icons/react';
import { CATEGORY_META, CAT_TEXT_VAR } from '../data/foods';

export default function FoodTag({ food, onRemove }) {
  const [showConfirm, setShowConfirm] = useState(false);
  const timerRef = useRef(null);
  const reduce = useReducedMotion();
  const meta = CATEGORY_META[food.category] || { emoji: '🍽️', color: 'var(--cat-staple)' };
  const textColor = CAT_TEXT_VAR[food.category] || 'var(--text-secondary)';

  const startLongPress = () => {
    timerRef.current = setTimeout(() => {
      setShowConfirm(true);
      if (navigator.vibrate) navigator.vibrate(15);
    }, 600);
  };

  const cancelLongPress = () => {
    clearTimeout(timerRef.current);
  };

  const handleRemove = (e) => {
    e.stopPropagation();
    onRemove(food._id);
  };

  return (
    <div className="relative inline-flex">
      <motion.span
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium cursor-pointer select-none"
        style={{
          background: meta.color,
          color: textColor,
          borderRadius: 'var(--radius-sm)',
        }}
        onTouchStart={startLongPress}
        onTouchEnd={cancelLongPress}
        onTouchMove={cancelLongPress}
        onMouseDown={startLongPress}
        onMouseUp={cancelLongPress}
        onMouseLeave={cancelLongPress}
        layout
        initial={reduce ? false : { scale: 0, opacity: 0 }}
        animate={reduce ? false : { scale: 1, opacity: 1 }}
        exit={reduce ? false : { scale: 0, opacity: 0 }}
      >
        <span className="text-xs">{meta.emoji}</span>
        <span className="max-w-[80px] truncate">{food.name}</span>
        <span className="font-number text-[10px] opacity-70">{food.kcal}kcal</span>
        <span
          className="ml-0.5 w-4 h-4 flex items-center justify-center rounded-full transition-colors"
          style={{ background: 'rgba(0,0,0,0.06)' }}
          onClick={handleRemove}
          role="button"
          aria-label="移除"
        >
          <X size={10} weight="bold" />
        </span>
      </motion.span>

      <AnimatePresence>
        {showConfirm && (
          <motion.div
            className="absolute -top-12 left-1/2 -translate-x-1/2 rounded-xl px-4 py-2.5 text-xs shadow-xl flex items-center gap-2 z-50 whitespace-nowrap"
            style={{
              background: 'rgba(255, 59, 48, 0.95)',
              boxShadow: '0 8px 25px rgba(255, 59, 48, 0.25)',
              color: 'white',
            }}
            initial={reduce ? false : { opacity: 0, y: 8 }}
            animate={reduce ? false : { opacity: 1, y: 0 }}
            exit={reduce ? false : { opacity: 0, y: 8 }}
          >
            <span>确认移除？</span>
            <button
              className="px-2.5 py-1 rounded-lg font-medium"
              style={{ background: 'rgba(255,255,255,0.25)' }}
              onClick={(e) => { e.stopPropagation(); handleRemove(e); setShowConfirm(false); }}
            >
              移除
            </button>
            <button
              className="px-2.5 py-1 rounded-lg"
              style={{ background: 'rgba(255,255,255,0.15)' }}
              onClick={(e) => { e.stopPropagation(); setShowConfirm(false); }}
            >
              取消
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
