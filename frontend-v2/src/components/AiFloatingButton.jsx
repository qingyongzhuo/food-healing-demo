import { motion, useReducedMotion } from 'framer-motion';
import { Sparkle } from '@phosphor-icons/react';
import { useUiStore } from '../stores/uiStore';

export default function AiFloatingButton() {
  const openAiDrawer = useUiStore(s => s.openAiDrawer);
  const reduce = useReducedMotion();

  return (
    <motion.button
      onClick={openAiDrawer}
      aria-label="AI营养师"
      initial={reduce ? false : { opacity: 0, scale: 0.8 }}
      animate={reduce ? false : { opacity: 1, scale: 1 }}
      transition={reduce ? {} : { duration: 0.3, ease: [0.32, 0.72, 0, 1], delay: 0.2 }}
      whileTap={reduce ? {} : { scale: 0.92 }}
      className="fixed z-20 flex flex-col items-center justify-center glass-overlay"
      style={{
        right: 'max(16px, calc((100vw - 448px) / 2))',
        bottom: 'calc(72px + env(safe-area-inset-bottom, 0px))',
        width: '52px',
        height: '52px',
        borderRadius: '50%',
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.6)',
      }}
    >
      <Sparkle size={20} weight="fill" color="var(--accent)" />
      <span
        className="text-[9px] font-medium leading-none mt-0.5"
        style={{ color: 'var(--accent)' }}
      >
        AI营养师
      </span>
    </motion.button>
  );
}
