import {
  House,
  ChartBar,
  Camera,
  Bell,
  User,
} from '@phosphor-icons/react';
import { useUiStore } from '../stores/uiStore';

const TABS = [
  { key: 'home', label: '首页', icon: House },
  { key: 'stats', label: '数据统计', icon: ChartBar },
  { key: 'photo', label: '拍照识菜', icon: Camera, center: true },
  { key: 'message', label: '消息', icon: Bell },
  { key: 'profile', label: '我的', icon: User },
];

export default function BottomTab() {
  const activeTab = useUiStore(s => s.activeTab);
  const setActiveTab = useUiStore(s => s.setActiveTab);
  const openPhotoModal = useUiStore(s => s.openPhotoModal);

  const handleClick = (tab) => {
    if (tab.key === 'photo') {
      openPhotoModal();
      return;
    }
    setActiveTab(tab.key);
  };

  return (
    <div
      className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-lg z-40 safe-bottom glass-overlay"
      style={{
        borderTop: '1px solid var(--border-color)',
      }}
    >
      <div className="flex items-center justify-around px-2 pt-2 pb-2">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;

          if (tab.center) {
            // 中间突出核心按钮 — 拍照识菜（当前页蓝色高亮）
            return (
              <button
                key={tab.key}
                onClick={() => handleClick(tab)}
                className="flex flex-col items-center gap-1 active:scale-95 transition-transform"
                aria-label={tab.label}
              >
                <div
                  className="w-12 h-12 rounded-full flex items-center justify-center transition-all"
                  style={{
                    background: 'var(--accent)',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.12)',
                    marginTop: '-18px',
                    border: isActive ? '2px solid var(--bg-primary)' : 'none',
                  }}
                >
                  <Icon size={22} weight="fill" color="#FFFFFF" />
                </div>
                <span
                  className="text-[10px] font-medium"
                  style={{ color: 'var(--accent)' }}
                >
                  {tab.label}
                </span>
              </button>
            );
          }

          return (
            <button
              key={tab.key}
              onClick={() => handleClick(tab)}
              className="flex flex-col items-center gap-1 px-3 py-1 active:scale-95 transition-transform"
              aria-label={tab.label}
            >
              <Icon
                size={22}
                weight={isActive ? 'fill' : 'regular'}
                color={isActive ? 'var(--accent)' : 'var(--text-tertiary)'}
              />
              <span
                className="text-[10px] font-medium"
                style={{
                  color: isActive ? 'var(--accent)' : 'var(--text-tertiary)',
                }}
              >
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
