import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useUiStore = create(
  persist(
    (set) => ({
      activeMeal: null,
      showSlidePanel: false,
      showProfile: false,
      chatExpanded: false,
      // 底部 Tab 当前页
      activeTab: 'home',
      // AI 抽屉（右下角悬浮按钮触发）
      showAiDrawer: false,
      // 拍照识菜弹窗（底部 Tab 拍照按钮触发）
      showPhotoModal: false,
      // 深浅色主题：'light' | 'dark'
      theme: 'light',
      // 通知开关
      notifyMeal: true,
      notifyAi: true,

      openSlidePanel(mealSlot) {
        set({ activeMeal: mealSlot, showSlidePanel: true });
      },

      closeSlidePanel() {
        set({ activeMeal: null, showSlidePanel: false });
      },

      toggleProfile() {
        set(state => ({ showProfile: !state.showProfile }));
      },

      toggleChat() {
        set(state => ({ chatExpanded: !state.chatExpanded }));
      },

      setActiveTab(tab) {
        set({ activeTab: tab });
      },

      openAiDrawer() {
        set({ showAiDrawer: true });
      },

      closeAiDrawer() {
        set({ showAiDrawer: false });
      },

      openPhotoModal() {
        set({ showPhotoModal: true });
      },

      closePhotoModal() {
        set({ showPhotoModal: false });
      },

      toggleTheme() {
        set(state => ({ theme: state.theme === 'light' ? 'dark' : 'light' }));
      },

      setNotify(key, value) {
        set({ [key]: value });
      },
    }),
    {
      name: 'food-ui',
      partialize: (state) => ({
        theme: state.theme,
        notifyMeal: state.notifyMeal,
        notifyAi: state.notifyAi,
      }),
    }
  )
);
