import { useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import { ChartBar } from '@phosphor-icons/react';
import { useAuthStore } from './stores/authStore';
import { useMealStore, useUserStore } from './stores/mealStore';
import { useUiStore } from './stores/uiStore';
import { MEAL_SLOTS } from './data/foods';
import AuthView from './components/AuthView';
import DiaryHeader from './components/DiaryHeader';
import NutritionOverview from './components/NutritionOverview';
import MealCard from './components/MealCard';
import NotificationsView from './components/NotificationsView';
import BottomTab from './components/BottomTab';
import AiFloatingButton from './components/AiFloatingButton';
import AiDrawer from './components/AiDrawer';
import FoodSlidePanel from './components/FoodSlidePanel';
import PhotoRecognition from './components/PhotoRecognition';
import ProfileView from './components/ProfileView';

export default function App() {
  const isLoggedIn = useAuthStore(s => s.isLoggedIn);
  const initAuth = useAuthStore(s => s.initAuth);
  const meals = useMealStore(s => s.meals);
  const target = useUserStore(s => s.target);
  const activeTab = useUiStore(s => s.activeTab);
  const theme = useUiStore(s => s.theme);

  // 应用启动时校验 token：若失效则由 handleUnauthorized 重置登录态
  useEffect(() => {
    initAuth();
  }, []);

  // 应用深浅色主题到 documentElement
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const toastStyle = {
    background: theme === 'dark' ? 'rgba(28, 28, 30, 0.92)' : 'rgba(255, 255, 255, 0.92)',
    backdropFilter: 'blur(20px) saturate(1.4)',
    WebkitBackdropFilter: 'blur(20px) saturate(1.4)',
    border: '1px solid var(--border-color)',
    color: 'var(--text-primary)',
    fontSize: '13px',
    borderRadius: '12px',
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
  };

  if (!isLoggedIn) {
    return (
      <>
        <AuthView />
        <Toaster position="top-center" toastOptions={{ style: toastStyle }} />
      </>
    );
  }

  // 仅在首页显示悬浮 AI 营养师按钮（拍照识菜页不显示，避免遮挡操作）
  const showFloatingAi = activeTab === 'home';

  return (
    <div className="min-h-[100dvh] max-w-lg mx-auto relative">
      {activeTab === 'profile' ? (
        <ProfileView />
      ) : activeTab === 'message' ? (
        <NotificationsView />
      ) : activeTab === 'stats' ? (
        <div className="flex flex-col items-center justify-center min-h-[60dvh] px-4 pb-32">
          <ChartBar size={36} weight="thin" color="var(--text-tertiary)" className="mb-3 opacity-40" />
          <p className="text-sm text-[var(--text-tertiary)]">数据统计功能即将上线</p>
        </div>
      ) : (
        <div className="px-5 pt-8 pb-32">
          <DiaryHeader />

          <div className="space-y-5">
            <NutritionOverview meals={meals} target={target} />

            {MEAL_SLOTS.map((slot) => (
              <MealCard key={slot.key} slot={slot} />
            ))}
          </div>
        </div>
      )}

      {/* 底部导航常驻 + 悬浮 AI（仅首页）+ AI 抽屉 */}
      <BottomTab />
      {showFloatingAi && <AiFloatingButton />}
      <AiDrawer />

      {/* 拍照识菜独立全屏页（z-30 覆盖在首页之上，底部 Tab 仍可见） */}
      <PhotoRecognition />

      {/* 其他覆盖层 */}
      <FoodSlidePanel />

      <Toaster position="top-center" toastOptions={{ style: toastStyle }} />
    </div>
  );
}
