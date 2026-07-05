import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { DEFAULT_TARGET } from '../data/foods';

export const useUserStore = create(
  persist(
    (set) => ({
      target: DEFAULT_TARGET,
      setTarget(target) {
        set({ target });
      },

      // 重置用户目标数据（用于切换用户时清理 A 用户的残留数据）
      resetUser() {
        set({ target: DEFAULT_TARGET });
      },
    }),
    {
      name: 'food-user',
    }
  )
);