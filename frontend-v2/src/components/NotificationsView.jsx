import { useState, useMemo } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  Bell,
  Alarm,
  Robot,
  ForkKnife,
  Check,
  X,
} from '@phosphor-icons/react';
import { useNotificationStore } from '../stores/notificationStore';
import toast from 'react-hot-toast';

const CATEGORIES = ['全部通知', '饮食提醒', 'AI 营养推送'];

// 图标映射 — 全部 2px 细线性（Phosphor regular）
const ICON_MAP = {
  alarm: Alarm,
  ai: Robot,
  plate: ForkKnife,
};

export default function NotificationsView() {
  const notifications = useNotificationStore(s => s.notifications);
  const getByCategory = useNotificationStore(s => s.getByCategory);
  const markAsRead = useNotificationStore(s => s.markAsRead);
  const removeAll = useNotificationStore(s => s.removeAll);
  const reduce = useReducedMotion();

  const [activeCat, setActiveCat] = useState('全部通知');
  const [detail, setDetail] = useState(null); // 选中的通知详情
  const [confirmClear, setConfirmClear] = useState(false);

  const list = useMemo(
    () => getByCategory(activeCat),
    [getByCategory, activeCat, notifications]
  );

  const handleViewDetail = (n) => {
    markAsRead(n.id);
    setDetail(n);
  };

  const handleClearAll = () => {
    removeAll();
    setConfirmClear(false);
    toast.success('已清空全部通知');
  };

  return (
    <>
      {/* 1. 顶部导航玻璃栏 */}
      <div
        className="sticky top-0 z-20 glass-overlay"
        style={{
          borderBottom: '1px solid var(--border-color)',
        }}
      >
        <div className="flex items-center justify-between px-5 py-3.5">
          <div className="w-16" />
          <h1 className="text-[17px] font-semibold" style={{ color: 'var(--text-primary)' }}>
            消息通知
          </h1>
          <button
            onClick={() => setConfirmClear(true)}
            disabled={notifications.length === 0}
            className="text-xs px-2 py-1 rounded-lg transition-colors disabled:opacity-40"
            style={{ color: 'var(--accent)' }}
          >
            一键清空
          </button>
        </div>

        {/* 2. 横向分类切换标签栏 */}
        <div className="px-5 pb-2.5 flex gap-2 overflow-x-auto scrollbar-none">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCat(cat)}
              className="px-3.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all active:scale-95"
              style={
                activeCat === cat
                  ? { background: 'var(--accent)', color: '#fff' }
                  : {
                      background: 'rgba(118, 118, 123, 0.08)',
                      color: 'var(--text-primary)',
                    }
              }
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* 3. 消息列表 / 4. 空状态 */}
      <div className="px-4 pt-4 pb-32">
        {list.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-2.5">
            {list.map(n => (
              <NotificationCard
                key={n.id}
                notification={n}
                onViewDetail={() => handleViewDetail(n)}
                onIgnore={() => {
                  useNotificationStore.getState().remove(n.id);
                  toast('已忽略');
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* 详情弹窗 */}
      <AnimatePresence>
        {detail && (
          <DetailModal detail={detail} onClose={() => setDetail(null)} reduce={reduce} />
        )}
      </AnimatePresence>

      {/* 一键清空确认弹窗 */}
      <AnimatePresence>
        {confirmClear && (
          <ConfirmDialog
            title="清空全部通知？"
            message="清空后将无法恢复，确定要清除所有消息吗？"
            confirmText="清空"
            onConfirm={handleClearAll}
            onCancel={() => setConfirmClear(false)}
            reduce={reduce}
          />
        )}
      </AnimatePresence>
    </>
  );
}

function NotificationCard({ notification, onViewDetail, onIgnore }) {
  const Icon = ICON_MAP[notification.icon] || Bell;
  const isPositive = notification.tone === 'positive';
  const iconColor = isPositive ? 'var(--success)' : 'var(--warning)';

  return (
    <div
      className="relative rounded-2xl p-3.5"
      style={{
        background: 'var(--glass-bg)',
        backdropFilter: 'var(--glass-blur)',
        WebkitBackdropFilter: 'var(--glass-blur)',
        border: '1px solid var(--border-color)',
        boxShadow: 'var(--glass-shadow)',
      }}
    >
      {/* 未读蓝色圆点 */}
      {!notification.read && (
        <span
          className="absolute top-3 left-3 w-2 h-2 rounded-full"
          style={{ background: 'var(--accent)' }}
        />
      )}

      <div className="flex gap-3">
        {/* 左侧线性功能图标 */}
        <div
          className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
          style={{
            background: isPositive ? 'var(--success-soft)' : 'var(--warning-soft)',
          }}
        >
          <Icon size={18} weight="regular" color={iconColor} />
        </div>

        {/* 中间内容 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3
              className="text-sm font-semibold truncate"
              style={{ color: 'var(--text-primary)' }}
            >
              {notification.title}
            </h3>
            <span
              className="text-[11px] flex-shrink-0 mt-0.5"
              style={{ color: 'var(--text-tertiary)' }}
            >
              {notification.time}
            </span>
          </div>
          <p
            className="text-xs mt-1 line-clamp-2"
            style={{ color: 'var(--text-secondary)' }}
          >
            {notification.body}
          </p>

          {/* 底部操作按钮 */}
          <div className="flex gap-4 mt-2.5">
            <button
              onClick={onViewDetail}
              className="text-xs font-medium transition-colors"
              style={{ color: 'var(--accent)' }}
            >
              查看详情
            </button>
            <button
              onClick={onIgnore}
              className="text-xs transition-colors"
              style={{ color: 'var(--text-tertiary)' }}
            >
              忽略
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <Bell size={48} weight="regular" color="var(--text-tertiary)" />
      <p className="text-sm mt-4 text-center" style={{ color: 'var(--text-tertiary)' }}>
        暂无通知，记录饮食后会收到专属营养提醒
      </p>
    </div>
  );
}

function DetailModal({ detail, onClose, reduce }) {
  return (
    <>
      <motion.div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(0, 0, 0, 0.25)' }}
        initial={reduce ? false : { opacity: 0 }}
        animate={reduce ? false : { opacity: 1 }}
        exit={reduce ? false : { opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        className="fixed left-1/2 top-1/2 z-50 w-[88%] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl p-5"
        style={{
          background: 'var(--glass-bg-strong)',
          backdropFilter: 'var(--glass-blur)',
          WebkitBackdropFilter: 'var(--glass-blur)',
          border: '1px solid var(--border-color)',
          boxShadow: '0 12px 40px rgba(0, 0, 0, 0.12)',
        }}
        initial={reduce ? false : { scale: 0.92, opacity: 0 }}
        animate={reduce ? false : { scale: 1, opacity: 1 }}
        exit={reduce ? false : { scale: 0.92, opacity: 0 }}
        transition={reduce ? {} : { type: 'spring', stiffness: 320, damping: 28 }}
      >
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            {detail.title}
          </h3>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-full"
            style={{ background: 'rgba(118, 118, 123, 0.12)', color: 'var(--text-secondary)' }}
            aria-label="关闭"
          >
            <X size={14} weight="bold" />
          </button>
        </div>
        <p className="text-[11px] mb-3" style={{ color: 'var(--text-tertiary)' }}>
          {detail.time}
        </p>
        <p
          className="text-sm whitespace-pre-line leading-relaxed"
          style={{ color: 'var(--text-primary)' }}
        >
          {detail.detail}
        </p>
        <button
          onClick={onClose}
          className="w-full h-10 mt-5 rounded-xl text-white text-sm font-medium btn-primary"
        >
          知道了
        </button>
      </motion.div>
    </>
  );
}

function ConfirmDialog({ title, message, confirmText, onConfirm, onCancel, reduce }) {
  return (
    <>
      <motion.div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(0, 0, 0, 0.25)' }}
        initial={reduce ? false : { opacity: 0 }}
        animate={reduce ? false : { opacity: 1 }}
        exit={reduce ? false : { opacity: 0 }}
        onClick={onCancel}
      />
      <motion.div
        className="fixed left-1/2 top-1/2 z-50 w-[80%] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-2xl overflow-hidden"
        style={{
          background: 'var(--glass-bg-strong)',
          backdropFilter: 'var(--glass-blur)',
          WebkitBackdropFilter: 'var(--glass-blur)',
          border: '1px solid var(--border-color)',
        }}
        initial={reduce ? false : { scale: 0.92, opacity: 0 }}
        animate={reduce ? false : { scale: 1, opacity: 1 }}
        exit={reduce ? false : { scale: 0.92, opacity: 0 }}
        transition={reduce ? {} : { type: 'spring', stiffness: 320, damping: 28 }}
      >
        <div className="px-5 pt-5 pb-4 text-center">
          <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            {title}
          </h3>
          <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {message}
          </p>
        </div>
        <div className="flex" style={{ borderTop: '1px solid var(--border-color)' }}>
          <button
            onClick={onCancel}
            className="flex-1 py-3 text-sm font-medium transition-colors"
            style={{ color: 'var(--text-primary)', borderRight: '1px solid var(--border-color)' }}
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 py-3 text-sm font-semibold transition-colors"
            style={{ color: 'var(--danger)' }}
          >
            {confirmText}
          </button>
        </div>
      </motion.div>
    </>
  );
}
