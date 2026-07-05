import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import toast from 'react-hot-toast';
import * as api from '../lib/api';

export const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isLoggedIn: false,
      authLoading: false,
      authError: '',

      // 仅重置状态，不发请求（供 401 自动登出使用，避免循环请求）
      resetAuth() {
        set({
          token: null,
          user: null,
          isLoggedIn: false,
          authLoading: false,
          authError: '',
        });
      },

      // 清除错误提示（用于切换模式 / 修改输入时）
      clearAuthError() {
        if (get().authError) set({ authError: '' });
      },

      async login(nickname, password) {
        set({ authLoading: true, authError: '' });
        try {
          const data = await api.login(nickname, password);
          const token = data.token || data.access_token;
          localStorage.setItem('token', token);
          set({
            token,
            user: data.user || { nickname },
            isLoggedIn: true,
            authLoading: false,
          });
          toast.success('登录成功');
        } catch (err) {
          set({ authError: err.message, authLoading: false });
        }
      },

      async register(nickname, password, phone) {
        set({ authLoading: true, authError: '' });
        try {
          const data = await api.register(nickname, password, phone);
          const token = data.token || data.access_token;
          localStorage.setItem('token', token);
          set({
            token,
            user: data.user || { nickname },
            isLoggedIn: true,
            authLoading: false,
          });
          toast.success('注册成功');
        } catch (err) {
          set({ authError: err.message, authLoading: false });
        }
      },

      async logout() {
        try {
          await api.logout();
        } catch (_) {}
        get().resetAuth();
        // 同步清除 persist 中间件的 localStorage 缓存，避免竞态恢复旧 token
        try { useAuthStore.persist.clearStorage(); } catch (_) {}
      },

      async fetchProfile() {
        // 不吞错：401 时 api.js 的 handleUnauthorized 会调 resetAuth
        const data = await api.getProfile();
        set({ user: data.user || data });
      },

      // 应用启动时校验 token：若失效则由 handleUnauthorized 重置登录态
      async initAuth() {
        const { token } = get();
        if (!token) return;
        try {
          await get().fetchProfile();
        } catch (_) {
          // fetchProfile 失败时：
          // - 401：handleUnauthorized 已调 resetAuth
          // - 网络/其他：保持登录态，避免误登出，下次请求再处理
        }
      },

      setUser(user) {
        set({ user });
      },
    }),
    {
      name: 'food-auth',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isLoggedIn: state.isLoggedIn,
      }),
    }
  )
);
