import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { DEFAULT_TARGET } from '../data/foods';
import { calcNutrition } from '../lib/nutrition';

const getToday = () => new Date().toISOString().slice(0, 10);

export const useMealStore = create(
  persist(
    (set, get) => ({
      meals: { breakfast: [], lunch: [], dinner: [], snack: [] },
      todayDate: getToday(),
      history: {},

      _ensureToday() {
        const today = getToday();
        const state = get();
        if (state.todayDate !== today) {
          // Save yesterday's meals to history
          const history = { ...state.history };
          history[state.todayDate] = JSON.parse(JSON.stringify(state.meals));
          set({ meals: { breakfast: [], lunch: [], dinner: [], snack: [] }, todayDate: today, history });
          return true;
        }
        return false;
      },

      addFood(mealSlot, food) {
        get()._ensureToday();
        set(state => {
          const meals = { ...state.meals };
          meals[mealSlot] = [...meals[mealSlot], { ...food, _id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}` }];
          return { meals };
        });
      },

      removeFood(mealSlot, foodId) {
        set(state => {
          const meals = { ...state.meals };
          meals[mealSlot] = meals[mealSlot].filter(f => f._id !== foodId);
          return { meals };
        });
      },

      clearMeal(mealSlot) {
        set(state => {
          const meals = { ...state.meals };
          meals[mealSlot] = [];
          return { meals };
        });
      },

      getNutrition() {
        const state = get();
        if (state.todayDate !== getToday()) return { kcal: 0, protein: 0, carb: 0, fat: 0 };
        return calcNutrition(state.meals);
      },
    }),
    {
      name: 'food-meals',
      partialize: (state) => ({ meals: state.meals, todayDate: state.todayDate, history: state.history }),
    }
  )
);

export { useUserStore } from './userStore';