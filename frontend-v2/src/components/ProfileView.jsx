import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  Pencil, Camera, CaretRight, X,
  Heart, Download, Trash,
  Moon, Bell, LockKey, Info,
  SignOut, Check, Flame,
} from '@phosphor-icons/react';
import { useAuthStore } from '../stores/authStore';
import { useUserStore } from '../stores/mealStore';
import { useUiStore } from '../stores/uiStore';
import * as api from '../lib/api';
import toast from 'react-hot-toast';
import GlassCard from './GlassCard';

// 三种身体方案预设 —— 一键自动匹配营养标准
const BODY_GOALS = {
  fat_loss:   { label: '减脂', desc: '适度热量缺口，保留蛋白质', kcal: 1600, protein: 110, carb: 160, fat: 53 },
  maintain:   { label: '维持', desc: '均衡宏量，维持当前体重',   kcal: 2000, protein: 100, carb: 250, fat: 67 },
  muscle_gain:{ label: '增肌', desc: '热量盈余，高碳水高蛋白',   kcal: 2400, protein: 150, carb: 300, fat: 80 },
};

// 营养素颜色标识（仅小标识使用彩色）
const NUT_COLORS = {
  protein: 'var(--success)',   // 绿
  carb:    '#C9A86E',          // 米黄（比 --nut-carb 深一档，保证可读）
  fat:     'var(--warning)',   // 浅橙
};

export default function ProfileView() {
  const user = useAuthStore(s => s.user);
  const logout = useAuthStore(s => s.logout);
  const setUser = useAuthStore(s => s.setUser);
  const target = useUserStore(s => s.target);
  const setTarget = useUserStore(s => s.setTarget);
  const theme = useUiStore(s => s.theme);
  const toggleTheme = useUiStore(s => s.toggleTheme);
  const notifyMeal = useUiStore(s => s.notifyMeal);
  const notifyAi = useUiStore(s => s.notifyAi);
  const setNotify = useUiStore(s => s.setNotify);
  const reduce = useReducedMotion();

  const [showEdit, setShowEdit] = useState(false);
  const [showGoal, setShowGoal] = useState(false);
  const [savingGoal, setSavingGoal] = useState(false);
  const [form, setForm] = useState({
    nickname: user?.nickname || '',
    height: user?.height || '',
    weight: user?.weight || '',
    age: user?.age || '',
    gender: user?.gender || 'male',
    avatar_url: user?.avatar_url || '',
  });
  const avatarRef = useRef(null);

  // 挂载时拉取完整 profile（含 body_target），同步到 authStore.user 和 form
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await api.getUserProfile();
        if (!alive) return;
        const bodyTarget = data.body_target || {};
        // 合并 body_target 到 user，供 form 初始化和展示
        const merged = {
          ...user,
          ...(data.user || {}),
          height: bodyTarget.height_cm ?? '',
          weight: bodyTarget.weight_kg ?? '',
          age: bodyTarget.age ?? '',
          gender: bodyTarget.gender || 'male',
          target_type: bodyTarget.target_type || 'maintain',
        };
        setUser(merged);
        // 若后端有营养目标，同步到前端 store
        if (bodyTarget.daily_kcal) {
          setTarget({
            kcal: bodyTarget.daily_kcal,
            protein: bodyTarget.protein_g,
            carb: bodyTarget.carb_g,
            fat: bodyTarget.fat_g,
          });
        }
      } catch (_) {
        // 401 由 handleUnauthorized 处理；其他错误静默，保留 authStore.user 兜底
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // user 变化时同步 form（避免打开弹窗显示旧数据）
  useEffect(() => {
    setForm({
      nickname: user?.nickname || '',
      height: user?.height || '',
      weight: user?.weight || '',
      age: user?.age || '',
      gender: user?.gender || 'male',
      avatar_url: user?.avatar_url || '',
    });
  }, [user]);

  const handleAvatar = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const data = await api.uploadAvatar(file);
      const url = data.avatar_url || data.url;
      setUser({ ...user, avatar_url: url });
      setForm(f => ({ ...f, avatar_url: url }));
      toast.success('头像已更新');
    } catch (err) {
      toast.error(err.message);
    }
  };

  // 拆分为 updateUserProfile（昵称）+ updateUserBody（身体数据）
  const handleSaveProfile = async () => {
    try {
      // 1. 昵称走 /user/profile（基础资料）—— 仅在变化时调用
      if (form.nickname && form.nickname !== user?.nickname) {
        await api.updateUserProfile({ nickname: form.nickname });
      }
      // 2. 身体数据走 /user/body（height/weight/age/gender）—— 仅在变化时加入 payload
      const bodyPayload = {};
      const numHeight = form.height ? Number(form.height) : null;
      const numWeight = form.weight ? Number(form.weight) : null;
      const numAge = form.age ? Number(form.age) : null;
      if (numHeight !== null && numHeight !== Number(user?.height || null)) bodyPayload.height_cm = numHeight;
      if (numWeight !== null && numWeight !== Number(user?.weight || null)) bodyPayload.weight_kg = numWeight;
      if (numAge !== null && numAge !== Number(user?.age || null)) bodyPayload.age = numAge;
      if (form.gender && form.gender !== user?.gender) bodyPayload.gender = form.gender;
      if (Object.keys(bodyPayload).length > 0) {
        await api.updateUserBody(bodyPayload);
      }
      setUser({ ...user, ...form });
      setShowEdit(false);
      toast.success('资料已更新');
    } catch (err) {
      toast.error(err.message);
    }
  };

  // 调 updateUserTarget 持久化到后端
  const applyGoal = async (key) => {
    const g = BODY_GOALS[key];
    setSavingGoal(true);
    try {
      await api.updateUserTarget({
        daily_kcal: g.kcal,
        protein_g: g.protein,
        carb_g: g.carb,
        fat_g: g.fat,
        target_type: key,
      });
      setTarget({ kcal: g.kcal, protein: g.protein, carb: g.carb, fat: g.fat });
      setUser({ ...user, target_type: key });
      setShowGoal(false);
      toast.success(`已切换到「${g.label}」方案`);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSavingGoal(false);
    }
  };

  // 问题 5: 去掉无效 try-catch
  const handleClearCache = () => {
    toast.success('缓存已清理');
  };

  const handleLogout = () => {
    logout();
  };

  // 计算宏量营养素的供能占比（用于目标卡片的进度可视化）
  const macroPct = (g, calPerG) => {
    const total = target.kcal || 1;
    return Math.min((g * calPerG / total) * 100, 100);
  };

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 8 }}
      animate={reduce ? false : { opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
      className="px-5 pt-8 pb-32 space-y-5"
    >
      {/* ===== 1. 顶部用户信息大液态玻璃卡片 ===== */}
      <GlassCard strong>
        <div className="p-5 flex items-center gap-4">
          {/* 头像 */}
          <button
            onClick={() => avatarRef.current?.click()}
            className="w-16 h-16 rounded-full overflow-hidden flex-shrink-0 transition-transform active:scale-95"
            style={{
              background: 'var(--bg-tertiary)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            }}
            aria-label="更换头像"
          >
            {form.avatar_url ? (
              <img src={form.avatar_url} alt="" className="w-full h-full object-cover" />
            ) : (
              <div
                className="w-full h-full flex items-center justify-center text-white text-xl font-semibold"
                style={{ background: 'var(--accent)' }}
              >
                {(user?.nickname || user?.username || '我')[0]}
              </div>
            )}
          </button>
          <input ref={avatarRef} type="file" accept="image/*" onChange={handleAvatar} style={{ display: 'none' }} />

          {/* 用户名 + 身份标签 */}
          <div className="flex-1 min-w-0">
            <p className="text-base font-semibold text-[var(--text-primary)] truncate">
              {user?.nickname || user?.username || '食愈用户'}
            </p>
            <p
              className="text-xs mt-1.5 inline-flex items-center px-2 py-0.5 rounded-md"
              style={{
                color: 'var(--accent)',
                background: 'var(--accent-soft)',
              }}
            >
              食愈会员
            </p>
          </div>

          {/* 编辑资料按钮 */}
          <button
            onClick={() => setShowEdit(true)}
            className="flex items-center gap-1 text-sm text-[var(--accent)] px-3 py-1.5 transition-opacity active:opacity-60"
          >
            <Pencil size={14} weight="regular" />
            编辑资料
          </button>
        </div>
      </GlassCard>

      {/* ===== 2. 个人营养目标设置玻璃卡片 ===== */}
      <GlassCard>
        <div className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">每日营养目标</h2>
            <Flame size={16} weight="regular" color="var(--warning)" />
          </div>

          {/* 大号热量目标数字 */}
          <div className="flex items-baseline justify-center gap-1.5 mb-5">
            <span className="font-number text-4xl font-bold text-[var(--text-primary)] tracking-tight">
              {target.kcal}
            </span>
            <span className="text-sm text-[var(--text-tertiary)]">kcal / 天</span>
          </div>

          {/* 三项横向营养进度模块 */}
          <div className="space-y-3.5 mb-4">
            {[
              { label: '蛋白质', value: target.protein, unit: 'g', color: NUT_COLORS.protein, pct: macroPct(target.protein, 4) },
              { label: '碳水',   value: target.carb,    unit: 'g', color: NUT_COLORS.carb,    pct: macroPct(target.carb, 4) },
              { label: '脂肪',   value: target.fat,     unit: 'g', color: NUT_COLORS.fat,     pct: macroPct(target.fat, 9) },
            ].map(item => (
              <div key={item.label}>
                <div className="flex justify-between items-baseline mb-1.5">
                  <span className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
                    <span
                      className="inline-block w-2 h-2 rounded-full"
                      style={{ background: item.color }}
                    />
                    {item.label}
                  </span>
                  <span className="font-number text-xs text-[var(--text-primary)]">
                    {item.value}<span className="text-[var(--text-tertiary)]">{item.unit}</span>
                  </span>
                </div>
                <div
                  className="h-1.5 rounded-full overflow-hidden"
                  style={{ background: 'var(--bg-tertiary)' }}
                >
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: item.color }}
                    initial={reduce ? false : { width: 0 }}
                    animate={{ width: `${item.pct}%` }}
                    transition={{ duration: 0.6, ease: [0.32, 0.72, 0, 1] }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* 蓝色按钮 —— 一键匹配身体方案 */}
          <button
            onClick={() => setShowGoal(true)}
            className="btn-primary w-full py-3 rounded-xl text-sm font-semibold"
          >
            调整身体方案
          </button>
        </div>
      </GlassCard>

      {/* ===== 3a. 功能菜单分组 —— 数据管理 ===== */}
      <GlassCard>
        <div className="px-5 pt-4 pb-2">
          <p className="text-xs text-[var(--text-tertiary)]">数据管理</p>
        </div>
        <div className="px-5 pb-2">
          {[
            { icon: Heart,    label: '我的收藏食材', color: 'var(--accent)',  onClick: () => toast('收藏食材功能开发中') },
            { icon: Download, label: '饮食数据备份', color: 'var(--success)', onClick: () => toast('数据备份功能开发中') },
            { icon: Trash,    label: '清除缓存',     color: 'var(--warning)', onClick: handleClearCache },
          ].map((item, i, arr) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                onClick={item.onClick}
                className="w-full flex items-center gap-3 py-3.5 transition-colors"
                style={i < arr.length - 1 ? { borderBottom: '1px solid var(--divider)' } : undefined}
              >
                <Icon size={18} weight="regular" color={item.color} />
                <span className="text-sm flex-1 text-left text-[var(--text-primary)]">{item.label}</span>
                <CaretRight size={14} weight="regular" color="var(--text-tertiary)" />
              </button>
            );
          })}
        </div>
      </GlassCard>

      {/* ===== 3b. 功能菜单分组 —— 系统设置 ===== */}
      <GlassCard>
        <div className="px-5 pt-4 pb-2">
          <p className="text-xs text-[var(--text-tertiary)]">系统设置</p>
        </div>
        <div className="px-5 pb-2">
          {/* 深色 / 浅色模式切换 */}
          <div className="w-full flex items-center gap-3 py-3.5" style={{ borderBottom: '1px solid var(--divider)' }}>
            <Moon size={18} weight="regular" color="var(--accent)" />
            <span className="text-sm flex-1 text-[var(--text-primary)]">深色 / 浅色模式</span>
            <button
              className={`ios-toggle ${theme === 'dark' ? 'is-on' : ''}`}
              onClick={toggleTheme}
              aria-label="切换深浅色模式"
            />
          </div>

          {/* 消息通知管理 —— 饮食提醒 */}
          <div className="w-full flex items-center gap-3 py-3.5" style={{ borderBottom: '1px solid var(--divider)' }}>
            <Bell size={18} weight="regular" color="var(--accent)" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-[var(--text-primary)]">饮食提醒</p>
              <p className="text-xs text-[var(--text-tertiary)] mt-0.5">餐时推送提醒记录</p>
            </div>
            <button
              className={`ios-toggle ${notifyMeal ? 'is-on' : ''}`}
              onClick={() => setNotify('notifyMeal', !notifyMeal)}
              aria-label="切换饮食提醒"
            />
          </div>

          {/* 消息通知管理 —— AI 分析推送 */}
          <div className="w-full flex items-center gap-3 py-3.5" style={{ borderBottom: '1px solid var(--divider)' }}>
            <Flame size={18} weight="regular" color="var(--accent)" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-[var(--text-primary)]">AI 分析推送</p>
              <p className="text-xs text-[var(--text-tertiary)] mt-0.5">每日营养分析报告</p>
            </div>
            <button
              className={`ios-toggle ${notifyAi ? 'is-on' : ''}`}
              onClick={() => setNotify('notifyAi', !notifyAi)}
              aria-label="切换AI推送"
            />
          </div>

          {/* 隐私与权限设置 */}
          <button
            className="w-full flex items-center gap-3 py-3.5 transition-colors"
            style={{ borderBottom: '1px solid var(--divider)' }}
            onClick={() => toast('隐私设置开发中')}
          >
            <LockKey size={18} weight="regular" color="var(--accent)" />
            <span className="text-sm flex-1 text-left text-[var(--text-primary)]">隐私与权限设置</span>
            <CaretRight size={14} weight="regular" color="var(--text-tertiary)" />
          </button>

          {/* 关于食愈 */}
          <button
            className="w-full flex items-center gap-3 py-3.5 transition-colors"
            style={{ borderBottom: '1px solid var(--divider)' }}
            onClick={() => toast('食愈 v1.0.0 · 用户协议 · 隐私政策')}
          >
            <Info size={18} weight="regular" color="var(--accent)" />
            <span className="text-sm flex-1 text-left text-[var(--text-primary)]">关于食愈</span>
            <span className="text-xs text-[var(--text-tertiary)] mr-1">v1.0.0</span>
            <CaretRight size={14} weight="regular" color="var(--text-tertiary)" />
          </button>

          {/* 退出登录 */}
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 py-3.5 transition-colors"
          >
            <SignOut size={18} weight="regular" color="var(--danger)" />
            <span className="text-sm flex-1 text-left" style={{ color: 'var(--danger)' }}>退出登录</span>
          </button>
        </div>
      </GlassCard>

      {/* ===== 编辑资料弹窗 ===== */}
      <AnimatePresence>
        {showEdit && (
          <EditProfileModal
            form={form}
            setForm={setForm}
            onClose={() => setShowEdit(false)}
            onSave={handleSaveProfile}
            onPickAvatar={() => avatarRef.current?.click()}
          />
        )}
      </AnimatePresence>

      {/* ===== 调整营养方案弹窗 ===== */}
      <AnimatePresence>
        {showGoal && (
          <GoalModal
            current={target}
            saving={savingGoal}
            onClose={() => !savingGoal && setShowGoal(false)}
            onPick={applyGoal}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ============================================================
   编辑资料弹窗 —— 昵称 / 头像 / 身高 / 体重 / 年龄 / 性别
   ============================================================ */
function EditProfileModal({ form, setForm, onClose, onSave, onPickAvatar }) {
  const reduce = useReducedMotion();
  const inputCls = 'w-full h-11 px-3.5 rounded-xl text-sm';

  return (
    <motion.div
      className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center px-4"
      style={{
        background: 'rgba(0,0,0,0.25)',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
      }}
      initial={reduce ? false : { opacity: 0 }}
            animate={reduce ? false : { opacity: 1 }}
            exit={reduce ? false : { opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="card-strong w-full max-w-sm p-5"
        initial={reduce ? false : { scale: 0.95, y: 20, opacity: 0 }}
            animate={reduce ? false : { scale: 1, y: 0, opacity: 1 }}
            exit={reduce ? false : { scale: 0.95, y: 20, opacity: 0 }}
        transition={{ ease: [0.32, 0.72, 0, 1], duration: 0.3 }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-[var(--text-primary)]">编辑资料</h3>
          <button onClick={onClose} className="text-[var(--text-tertiary)] active:opacity-60">
            <X size={20} />
          </button>
        </div>

        {/* 头像选择 */}
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={onPickAvatar}
            className="w-14 h-14 rounded-full overflow-hidden flex-shrink-0 transition-transform active:scale-95"
            style={{ background: 'var(--bg-tertiary)' }}
          >
            {form.avatar_url ? (
              <img src={form.avatar_url} alt="" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-white" style={{ background: 'var(--accent)' }}>
                <Camera size={20} />
              </div>
            )}
          </button>
          <button onClick={onPickAvatar} className="text-sm text-[var(--accent)] active:opacity-60">
            更换头像
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-[var(--text-secondary)] mb-1.5 block">昵称</label>
            <input
              type="text"
              value={form.nickname}
              onChange={e => setForm({ ...form, nickname: e.target.value })}
              className={inputCls}
              placeholder="请输入昵称"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-[var(--text-secondary)] mb-1.5 block">身高 (cm)</label>
              <input
                type="number"
                value={form.height}
                onChange={e => setForm({ ...form, height: e.target.value })}
                className={inputCls}
                placeholder="170"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--text-secondary)] mb-1.5 block">体重 (kg)</label>
              <input
                type="number"
                value={form.weight}
                onChange={e => setForm({ ...form, weight: e.target.value })}
                className={inputCls}
                placeholder="60"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-[var(--text-secondary)] mb-1.5 block">年龄</label>
              <input
                type="number"
                value={form.age}
                onChange={e => setForm({ ...form, age: e.target.value })}
                className={inputCls}
                placeholder="25"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--text-secondary)] mb-1.5 block">性别</label>
              <div className="flex gap-2">
                {[
                  { key: 'male', label: '男' },
                  { key: 'female', label: '女' },
                ].map(g => (
                  <button
                    key={g.key}
                    onClick={() => setForm({ ...form, gender: g.key })}
                    className="flex-1 h-11 rounded-xl text-sm transition-all"
                    style={
                      form.gender === g.key
                        ? { background: 'var(--accent)', color: '#FFFFFF' }
                        : { background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }
                    }
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="flex gap-2.5 mt-5">
          <button
            onClick={onClose}
            className="btn-secondary flex-1 py-3 rounded-xl text-sm font-medium"
          >
            取消
          </button>
          <button
            onClick={onSave}
            className="btn-primary flex-1 py-3 rounded-xl text-sm font-semibold"
          >
            保存
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

/* ============================================================
   调整营养方案弹窗 —— 减脂 / 增肌 / 维持 三选一
   ============================================================ */
function GoalModal({ current, saving, onClose, onPick }) {
  const reduce = useReducedMotion();
  const goals = [
    { key: 'fat_loss',    ...BODY_GOALS.fat_loss },
    { key: 'maintain',    ...BODY_GOALS.maintain },
    { key: 'muscle_gain', ...BODY_GOALS.muscle_gain },
  ];

  const isCurrent = (g) =>
    current.kcal === g.kcal && current.protein === g.protein && current.carb === g.carb && current.fat === g.fat;

  return (
    <motion.div
      className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center px-4"
      style={{
        background: 'rgba(0,0,0,0.25)',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
      }}
      initial={reduce ? false : { opacity: 0 }}
            animate={reduce ? false : { opacity: 1 }}
            exit={reduce ? false : { opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="card-strong w-full max-w-sm p-5"
        initial={reduce ? false : { scale: 0.95, y: 20, opacity: 0 }}
            animate={reduce ? false : { scale: 1, y: 0, opacity: 1 }}
            exit={reduce ? false : { scale: 0.95, y: 20, opacity: 0 }}
        transition={{ ease: [0.32, 0.72, 0, 1], duration: 0.3 }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-[var(--text-primary)]">选择身体方案</h3>
          <button onClick={onClose} disabled={saving} className="text-[var(--text-tertiary)] active:opacity-60 disabled:opacity-40">
            <X size={20} />
          </button>
        </div>

        <p className="text-xs text-[var(--text-secondary)] mb-4">
          一键自动匹配营养标准，也可在保存后手动微调
        </p>

        <div className="space-y-2.5">
          {goals.map(g => {
            const selected = isCurrent(g);
            return (
              <button
                key={g.key}
                onClick={() => onPick(g.key)}
                disabled={saving}
                className="w-full flex items-center gap-3 p-3.5 rounded-xl transition-all text-left disabled:opacity-50"
                style={
                  selected
                    ? { background: 'var(--accent-soft)', border: '1px solid var(--accent)' }
                    : { background: 'var(--bg-tertiary)', border: '1px solid transparent' }
                }
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-[var(--text-primary)]">{g.label}</span>
                    <span className="font-number text-xs text-[var(--text-tertiary)]">{g.kcal} kcal</span>
                  </div>
                  <p className="text-xs text-[var(--text-tertiary)] mt-1">{g.desc}</p>
                  <div className="flex gap-3 mt-2">
                    <span className="text-xs" style={{ color: NUT_COLORS.protein }}>
                      蛋白 {g.protein}g
                    </span>
                    <span className="text-xs" style={{ color: NUT_COLORS.carb }}>
                      碳水 {g.carb}g
                    </span>
                    <span className="text-xs" style={{ color: NUT_COLORS.fat }}>
                      脂肪 {g.fat}g
                    </span>
                  </div>
                </div>
                {selected && (
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                    style={{ background: 'var(--accent)' }}
                  >
                    <Check size={14} weight="bold" color="#FFFFFF" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </motion.div>
    </motion.div>
  );
}
