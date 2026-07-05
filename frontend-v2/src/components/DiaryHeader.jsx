import { format } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { GearSix } from '@phosphor-icons/react';
import { useUiStore } from '../stores/uiStore';
import { useAuthStore } from '../stores/authStore';
import { useMealStore } from '../stores/mealStore';
import { useUserStore } from '../stores/mealStore';
import { calcNutrition, generateAiSummary } from '../lib/nutrition';
import { useMemo } from 'react';

const WEEKDAY_MAP = {
  0: '星期日', 1: '星期一', 2: '星期二', 3: '星期三',
  4: '星期四', 5: '星期五', 6: '星期六',
};

export default function DiaryHeader() {
  const setActiveTab = useUiStore(s => s.setActiveTab);
  const user = useAuthStore(s => s.user);
  const meals = useMealStore(s => s.meals);
  const target = useUserStore(s => s.target);

  const today = format(new Date(), 'yyyy.MM.dd');
  const weekday = WEEKDAY_MAP[new Date().getDay()];
  const summary = useMemo(() => generateAiSummary(meals, target), [meals, target]);

  const goProfile = () => setActiveTab('profile');

  return (
    <div className="flex items-start justify-between pb-5">
      <div className="flex-1 min-w-0">
        <h1 className="text-xl font-bold text-[var(--text-primary)] tracking-tight leading-tight">
          {today} {weekday}
        </h1>
        <p className="text-xs text-[var(--text-secondary)] mt-1.5 leading-relaxed line-clamp-2">
          {summary}
        </p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={goProfile}
          className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-semibold overflow-hidden transition-transform active:scale-95"
          style={{
            background: 'var(--accent)',
            boxShadow: '0 1px 3px rgba(0, 122, 255, 0.25)',
          }}
          aria-label="个人中心"
        >
          {user?.avatar_url ? (
            <img src={user.avatar_url} alt="" className="w-full h-full object-cover" />
          ) : (
            (user?.nickname || user?.username || '我')[0]
          )}
        </button>
        <button
          onClick={goProfile}
          className="w-9 h-9 rounded-full flex items-center justify-center transition-colors active:scale-95"
          style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-secondary)',
          }}
          aria-label="设置"
        >
          <GearSix size={17} />
        </button>
      </div>
    </div>
  );
}
