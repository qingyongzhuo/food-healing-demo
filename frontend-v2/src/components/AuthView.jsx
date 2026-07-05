import { useState, useEffect } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import {
  User,
  Lock,
  Phone,
  Check,
  ForkKnife,
  AppleLogo,
  WechatLogo,
  Key,
  Heart,
  Leaf,
} from '@phosphor-icons/react';
import toast from 'react-hot-toast';
import { useAuthStore } from '../stores/authStore';

export default function AuthView() {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [agreed, setAgreed] = useState(false);
  const { login, register, authLoading, authError, clearAuthError } = useAuthStore();
  const reduce = useReducedMotion();

  const handleSwitchMode = (next) => {
    if (next === mode) return;
    setMode(next);
    setPhone('');
    clearAuthError();
  };

  useEffect(() => {
    clearAuthError();
  }, [username, password, phone, clearAuthError]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!agreed || authLoading) return;
    if (mode === 'login') {
      login(username, password);
    } else {
      register(username, password, phone || undefined);
    }
  };

  const handleForgotPassword = () => {
    toast('忘记密码功能即将上线（需绑定手机号）', { icon: <Key size={16} /> });
  };

  const handleThirdParty = (type) => {
    toast(`${type}登录即将上线`, {
      icon: type === '苹果' ? <AppleLogo size={16} /> : <Heart size={16} />,
    });
  };

  return (
    <div className="min-h-[100dvh] max-w-lg mx-auto flex flex-col px-7 pt-20 pb-10 relative overflow-hidden">
      {/* 背景光晕装饰 — Sunset Coral 弱光晕，仅做氛围 */}
      <div
        className="absolute -top-24 -right-24 w-72 h-72 rounded-full opacity-20 pointer-events-none"
        style={{
          background:
            'radial-gradient(circle, rgba(224, 120, 86, 0.18) 0%, transparent 70%)',
        }}
      />
      <div
        className="absolute top-40 -left-20 w-56 h-56 rounded-full opacity-15 pointer-events-none"
        style={{
          background:
            'radial-gradient(circle, rgba(224, 120, 86, 0.10) 0%, transparent 70%)',
        }}
      />

      {/* 品牌区 — 紧凑化，把空间让给表单 */}
      <motion.div
        className="flex flex-col items-center mb-10 relative z-10"
        initial={reduce ? false : { opacity: 0, y: 16 }}
        animate={reduce ? false : { opacity: 1, y: 0 }}
        transition={reduce ? {} : { duration: 0.6, ease: [0.32, 0.72, 0, 1] }}
      >
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 relative"
          style={{
            background: 'linear-gradient(135deg, #E07856 0%, #D86A48 100%)',
            boxShadow:
              '0 6px 16px rgba(224, 120, 86, 0.30), 0 2px 4px rgba(224, 120, 86, 0.18)',
          }}
        >
          <ForkKnife size={26} weight="fill" color="#FFFFFF" />
          <div
            className="absolute -top-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center"
            style={{ background: '#FFFFFF', boxShadow: '0 1px 3px rgba(0, 0, 0, 0.10)' }}
          >
            <Leaf size={10} weight="fill" color="#E07856" />
          </div>
        </div>

        <h1
          className="text-3xl font-bold mb-1.5"
          style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}
        >
          食愈
        </h1>
        <p
          className="text-sm font-medium"
          style={{ color: 'var(--text-secondary)' }}
        >
          好好吃饭，慢慢变好
        </p>
      </motion.div>

      {/* 表单卡片 */}
      <motion.div
        className="relative z-10"
        initial={reduce ? false : { opacity: 0, y: 20 }}
        animate={reduce ? false : { opacity: 1, y: 0 }}
        transition={
          reduce ? {} : { duration: 0.6, ease: [0.32, 0.72, 0, 1], delay: 0.1 }
        }
      >
        <div
          className="rounded-3xl p-7"
          style={{
            background: '#FFFFFF',
            boxShadow:
              '0 4px 24px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.04)',
            border: '1px solid rgba(0, 0, 0, 0.04)',
          }}
        >
          {/* 分段切换 */}
          <div
            className="flex rounded-2xl p-1 mb-6"
            style={{ background: 'var(--bg-tertiary)' }}
          >
            <button
              type="button"
              onClick={() => handleSwitchMode('login')}
              className={`flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                mode === 'login' ? '' : 'text-[var(--text-tertiary)]'
              }`}
              style={
                mode === 'login'
                  ? {
                      background: '#FFFFFF',
                      color: 'var(--text-primary)',
                      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.08)',
                    }
                  : {}
              }
            >
              登录
            </button>
            <button
              type="button"
              onClick={() => handleSwitchMode('register')}
              className={`flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                mode === 'register' ? '' : 'text-[var(--text-tertiary)]'
              }`}
              style={
                mode === 'register'
                  ? {
                      background: '#FFFFFF',
                      color: 'var(--text-primary)',
                      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.08)',
                    }
                  : {}
              }
            >
              注册
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* 昵称 */}
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                <User size={18} color="var(--text-tertiary)" weight="regular" />
              </span>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={mode === 'login' ? '输入昵称' : '设置昵称'}
                required
                maxLength={50}
                className="w-full h-12 pl-12 pr-4 rounded-2xl text-sm"
                autoComplete="username"
              />
            </div>

            {/* 密码 */}
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                <Lock size={18} color="var(--text-tertiary)" weight="regular" />
              </span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={
                  mode === 'login' ? '输入密码' : '设置登录密码（至少 6 位）'
                }
                required
                minLength={6}
                maxLength={64}
                className="w-full h-12 pl-12 pr-4 rounded-2xl text-sm"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>

            {/* 注册：手机号 */}
            {mode === 'register' && (
              <div>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                    <Phone size={18} color="var(--text-tertiary)" weight="regular" />
                  </span>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) =>
                      setPhone(e.target.value.replace(/\D/g, '').slice(0, 11))
                    }
                    placeholder="绑定手机号（选填）"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={11}
                    className="w-full h-12 pl-12 pr-4 rounded-2xl text-sm"
                    autoComplete="tel"
                  />
                </div>
                <p
                  className="text-[11px] mt-1.5 ml-1"
                  style={{ color: 'var(--text-tertiary)' }}
                >
                  不填写也可完成注册
                </p>
              </div>
            )}

            {/* 登录：忘记密码 */}
            {mode === 'login' && (
              <div className="text-right -mt-1">
                <button
                  type="button"
                  onClick={handleForgotPassword}
                  className="text-xs active:opacity-60 transition-opacity"
                  style={{ color: 'var(--accent)' }}
                >
                  忘记密码？
                </button>
              </div>
            )}

            {/* 错误提示 */}
            {authError && (
              <p
                className="text-xs text-center -mt-1"
                style={{ color: 'var(--warning)' }}
              >
                {authError}
              </p>
            )}

            {/* 协议复选框 */}
            <button
              type="button"
              onClick={() => setAgreed(!agreed)}
              className="flex items-center gap-2.5 py-1 active:opacity-60 transition-opacity"
            >
              <div
                className="w-5 h-5 rounded-[6px] flex items-center justify-center transition-all shrink-0"
                style={
                  agreed
                    ? { background: 'var(--brand)' }
                    : {
                        border: '1.5px solid var(--border-color)',
                        background: 'transparent',
                      }
                }
              >
                {agreed && <Check size={12} weight="bold" color="#FFFFFF" />}
              </div>
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                同意用户协议与隐私政策
              </span>
            </button>

            {/* 主按钮 */}
            <button
              type="submit"
              disabled={!agreed || authLoading}
              className="w-full h-12 rounded-2xl text-white text-sm font-semibold disabled:opacity-40 btn-primary mt-1"
            >
              {authLoading ? '请稍等...' : mode === 'login' ? '登录' : '完成注册'}
            </button>
          </form>
        </div>
      </motion.div>

      {/* 第三方登录 — 弱化为纯图标，避免与主按钮抢戏 */}
      <div className="mt-8 relative z-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 h-px" style={{ background: 'var(--border-color)' }} />
          <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
            其他登录方式
          </span>
          <div className="flex-1 h-px" style={{ background: 'var(--border-color)' }} />
        </div>
        <div className="flex justify-center gap-8">
          <button
            type="button"
            onClick={() => handleThirdParty('苹果')}
            aria-label="苹果登录"
            className="flex items-center justify-center active:scale-90 transition-transform"
          >
            <AppleLogo size={26} color="var(--text-secondary)" weight="regular" />
          </button>
          <button
            type="button"
            onClick={() => handleThirdParty('微信')}
            aria-label="微信登录"
            className="flex items-center justify-center active:scale-90 transition-transform"
          >
            <WechatLogo size={26} color="var(--success)" weight="regular" />
          </button>
        </div>
      </div>

      {/* 底部协议（精简版，避免与上方复选框重复） */}
      <p
        className="text-center text-[10px] mt-auto pt-6 leading-relaxed"
        style={{ color: 'var(--text-tertiary)' }}
      >
        登录即代表同意
        <span className="ml-1" style={{ color: 'var(--text-secondary)' }}>
          《用户服务协议》
        </span>
        <span className="ml-1" style={{ color: 'var(--text-secondary)' }}>
          《隐私政策》
        </span>
      </p>
    </div>
  );
}
