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
    }),
    {
      name: 'food-user',
    }
  )
);