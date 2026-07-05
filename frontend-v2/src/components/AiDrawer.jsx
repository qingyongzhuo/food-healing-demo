import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  PaperPlaneTilt,
  Spinner,
  Sparkle,
  Trash,
  Archive,
  CaretLeft,
  Camera,
  ChatCircle,
  ClipboardText,
  Hourglass,
} from '@phosphor-icons/react';
import toast from 'react-hot-toast';
import { useChat } from '../hooks/useChat';
import { usePhotoRecognition } from '../hooks/usePhotoRecognition';
import { useMealStore, useUserStore } from '../stores/mealStore';
import { useUiStore } from '../stores/uiStore';
import { generateAiSummary, calcNutrition } from '../lib/nutrition';
import GlassCard from './GlassCard';

/**
 * AI 营养师聊天页 — 独立全屏页面（非弹窗）
 * 层级：顶部导航玻璃栏 → 今日饮食简报 → 对话记录区 → 快捷指令栏 → 底部输入栏
 * 复用 useChat 流式对话 + usePhotoRecognition 拍照识菜
 */
export default function AiDrawer() {
  const showAiDrawer = useUiStore(s => s.showAiDrawer);
  const closeAiDrawer = useUiStore(s => s.closeAiDrawer);
  const meals = useMealStore(s => s.meals);
  const target = useUserStore(s => s.target);
  const { messages, isStreaming, sendMessage, clearMessages } = useChat();
  const { startRecognize, isRecognizing, progress } = usePhotoRecognition();
  const reduce = useReducedMotion();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileRef = useRef(null);

  const summary = generateAiSummary(meals, target);

  // 快捷指令（输入框上方横向滚动）
  const QUICK_COMMANDS = [
    '今日饮食分析',
    '减脂午餐推荐',
    '低卡晚餐搭配',
    '热量超标调整方案',
    '增肌高蛋白食谱',
  ];

  // 食谱推荐小卡片
  const RECIPE_CARDS = [
    {
      key: 'high-protein-dinner',
      tag: '晚餐推荐',
      title: '高蛋白低脂晚餐搭配',
      prompt: '请给我一份高蛋白低脂的晚餐搭配方案，包含具体菜品和分量。',
    },
    {
      key: 'low-cal-balanced',
      tag: '一日食谱',
      title: '低卡均衡一日食谱',
      prompt: '请给我一份低卡均衡的一日三餐食谱，总热量控制在1500kcal以内。',
    },
  ];

  useEffect(() => {
    if (showAiDrawer) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [showAiDrawer]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 统一发送逻辑（手动输入 / 快捷指令 / 食谱卡片 / 图片识别结果 都走这里）
  const sendText = (text) => {
    if (!text.trim() || isStreaming) return;
    const allFoods = Object.values(meals).flat();
    const nutrition = calcNutrition(meals);
    sendMessage(text, {
      today_foods: allFoods.map(f => ({ name: f.name, category: f.category, kcal: f.kcal })),
      nutrition,
      target,
    });
  };

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    sendText(text);
  };

  const handleQuickSend = (cmd) => {
    if (isStreaming) return;
    sendText(cmd);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClear = () => {
    if (messages.length === 0) {
      toast('暂无对话记录', { icon: <ChatCircle size={16} /> });
      return;
    }
    clearMessages();
    toast.success('已清空对话');
  };

  const handleHistory = () => {
    toast('历史存档功能即将上线', { icon: <ClipboardText size={16} /> });
  };

  // 图片上传 → 识别 → 自动发送给 AI 分析
  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = ''; // 重置以便重复选择同一文件

    // streaming 时禁止识别（避免结果静默丢弃）
    if (isStreaming) {
      toast('AI 正在回复，请稍后再上传图片', { icon: <Hourglass size={16} /> });
      return;
    }

    const dish = await startRecognize(file);
    if (!dish) return;

    // 双重保险：识别完成后再检查一次 streaming 状态
    if (isStreaming) {
      toast('识别完成，但 AI 正在回复，请稍后点击重试', { icon: <Hourglass size={16} /> });
      return;
    }

    const prompt = `我刚吃了这道菜：${dish.name}（${dish.category}，约${dish.kcal || 0}kcal，蛋白质${dish.protein || 0}g）。请帮我分析营养并给出优化建议。`;
    sendText(prompt);
  };

  return (
    <AnimatePresence>
      {showAiDrawer && (
        <motion.div
          initial={reduce ? false : { x: '100%' }}
          animate={reduce ? false : { x: 0 }}
          exit={reduce ? false : { x: '100%' }}
          transition={reduce ? {} : { duration: 0.32, ease: [0.32, 0.72, 0, 1] }}
          className="fixed top-0 right-0 z-50 h-[100dvh] w-full max-w-lg flex flex-col"
          style={{
            background: 'var(--bg-primary)',
            boxShadow: '-8px 0 32px rgba(0, 0, 0, 0.08)',
          }}
        >
          {/* 1. 顶部导航玻璃栏 */}
          <header
            className="flex items-center justify-between px-4 py-3 safe-top glass-overlay"
            style={{
              borderBottom: '1px solid var(--border-color)',
            }}
          >
            {/* 左：返回箭头 */}
            <button
              onClick={closeAiDrawer}
              aria-label="返回首页"
              className="w-9 h-9 rounded-full flex items-center justify-center active:scale-90 transition-transform"
              style={{ background: 'var(--bg-tertiary)' }}
            >
              <CaretLeft size={18} weight="bold" color="var(--text-primary)" />
            </button>

            {/* 中：标题 */}
            <h1 className="text-base font-semibold text-[var(--text-primary)]">
              AI 营养师
            </h1>

            {/* 右：清空 + 历史 */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleClear}
                aria-label="清空对话"
                disabled={isStreaming}
                className="w-9 h-9 rounded-full flex items-center justify-center active:scale-90 transition-transform disabled:opacity-30"
                style={{ background: 'var(--bg-tertiary)' }}
              >
                <Trash size={16} color="var(--text-secondary)" />
              </button>
              <button
                onClick={handleHistory}
                aria-label="历史分析存档"
                className="w-9 h-9 rounded-full flex items-center justify-center active:scale-90 transition-transform"
                style={{ background: 'var(--bg-tertiary)' }}
              >
                <Archive size={16} color="var(--text-secondary)" />
              </button>
            </div>
          </header>

          {/* 2 & 3. 滚动区：今日饮食简报 + 对话记录 */}
          <div className="flex-1 overflow-y-auto scrollbar-none">
            {/* 2. 今日饮食自动分析液态玻璃大卡片（页面第二视觉重点） */}
            <div className="px-4 pt-4 pb-2">
              <GlassCard strong>
                <div className="p-5">
                  {/* 小标题 */}
                  <div className="flex items-center gap-1.5 mb-2.5">
                    <Sparkle size={14} weight="fill" color="var(--accent)" />
                    <span className="text-xs font-semibold text-[var(--text-primary)]">
                      今日饮食简报
                    </span>
                  </div>

                  {/* 核心总结文字 */}
                  <p className="text-sm leading-relaxed text-[var(--text-primary)] mb-3.5">
                    {summary}
                  </p>

                  {/* 2 个横向快捷食谱推荐小卡片 */}
                  <div className="grid grid-cols-2 gap-2.5 mb-3">
                    {RECIPE_CARDS.map((card) => (
                      <button
                        key={card.key}
                        onClick={() => handleQuickSend(card.prompt)}
                        disabled={isStreaming}
                        className="text-left p-3 active:scale-95 disabled:opacity-50 transition-transform"
                        style={{
                          background: 'var(--glass-bg)',
                          border: '1px solid var(--glass-border)',
                          borderRadius: '12px',
                          backdropFilter: 'var(--glass-blur)',
                          WebkitBackdropFilter: 'var(--glass-blur)',
                        }}
                      >
                        <div className="text-[10px] text-[var(--text-tertiary)] mb-1">
                          {card.tag}
                        </div>
                        <div className="text-xs font-medium text-[var(--text-primary)] leading-tight">
                          {card.title}
                        </div>
                      </button>
                    ))}
                  </div>

                  {/* 底部小字浅灰 */}
                  <p className="text-[10px] text-[var(--text-tertiary)]">
                    数据同步今日全部饮食记录
                  </p>
                </div>
              </GlassCard>
            </div>

            {/* 3. 对话聊天记录区 */}
            <div className="px-4 py-3 space-y-3">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center py-10">
                  <p className="text-sm text-[var(--text-tertiary)] text-center leading-relaxed max-w-[260px]">
                    有任何饮食、减脂、营养问题都可以咨询营养师
                  </p>
                </div>
              )}

              {messages.map((msg, i) => {
                const isLastAi = msg.role === 'ai' && i === messages.length - 1;
                const isThinking = isLastAi && isStreaming && !msg.text;
                return (
                  <motion.div
                    key={i}
                    initial={reduce ? false : { opacity: 0, y: 8 }}
                    animate={reduce ? false : { opacity: 1, y: 0 }}
                    transition={reduce ? {} : { duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] px-3.5 py-2.5 text-sm leading-relaxed ${msg.role === 'user'
                        ? 'text-white'
                        : 'text-[var(--text-primary)]'
                        }`}
                      style={
                        msg.role === 'user'
                          ? {
                            background: 'var(--accent)',
                            borderRadius: '16px 16px 4px 16px',
                          }
                          : {
                            background: 'var(--glass-bg)',
                            border: '1px solid var(--glass-border)',
                            borderRadius: '16px 16px 16px 4px',
                            backdropFilter: 'var(--glass-blur)',
                            WebkitBackdropFilter: 'var(--glass-blur)',
                          }
                      }
                    >
                      {isThinking ? (
                        <span className="inline-flex items-center gap-1.5 text-[var(--text-secondary)]">
                          <Spinner size={12} className="animate-spin" style={{ color: 'var(--accent)' }} />
                          AI 正在思考中
                          <span className="inline-flex gap-0.5 ml-0.5">
                            <span className="inline-block w-1 h-1 rounded-full animate-bounce" style={{ background: 'var(--text-tertiary)', animationDelay: '0ms' }} />
                            <span className="inline-block w-1 h-1 rounded-full animate-bounce" style={{ background: 'var(--text-tertiary)', animationDelay: '150ms' }} />
                            <span className="inline-block w-1 h-1 rounded-full animate-bounce" style={{ background: 'var(--text-tertiary)', animationDelay: '300ms' }} />
                          </span>
                        </span>
                      ) : (
                        <>
                          {msg.text}
                          {msg.role === 'ai' && isStreaming && isLastAi && (
                            <span
                              className="inline-block w-1.5 h-3.5 ml-0.5 animate-pulse align-middle rounded-sm"
                              style={{ background: 'var(--accent)' }}
                            />
                          )}
                        </>
                      )}
                    </div>
                  </motion.div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* 4. 快捷指令横向滚动栏 */}
          <div
            className="px-4 py-2.5 overflow-x-auto scrollbar-none"
            style={{
              background: 'rgba(255, 255, 255, 0.90)',
              borderTop: '1px solid var(--border-soft)',
            }}
          >
            <div className="flex gap-2">
              {QUICK_COMMANDS.map((cmd) => (
                <button
                  key={cmd}
                  onClick={() => handleQuickSend(cmd)}
                  disabled={isStreaming || isRecognizing}
                  className="flex-shrink-0 px-3 py-1.5 rounded-full text-xs whitespace-nowrap active:scale-95 disabled:opacity-50 transition-transform"
                  style={{
                    background: 'var(--bg-tertiary)',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  {cmd}
                </button>
              ))}
            </div>
          </div>

          {/* 5. 底部固定输入操作玻璃栏 */}
          <div
            className="px-4 pt-3 pb-4 safe-bottom glass-overlay"
            style={{
              borderTop: '1px solid var(--border-color)',
            }}
          >
            <div className="flex items-center gap-2.5">
              {/* 左：图片上传图标 */}
              <button
                onClick={() => fileRef.current?.click()}
                aria-label="拍摄菜品AI识别"
                disabled={isStreaming || isRecognizing}
                className="relative w-11 h-11 rounded-full flex items-center justify-center active:scale-90 transition-transform disabled:opacity-40"
                style={{ background: 'var(--bg-tertiary)' }}
              >
                {isRecognizing ? (
                  <>
                    <Spinner size={18} className="animate-spin" style={{ color: 'var(--accent)' }} />
                    {progress > 0 && (
                      <span
                        className="absolute -top-1 -right-1 text-[9px] font-number font-bold leading-none px-1 py-0.5 rounded-full text-white"
                        style={{ background: 'var(--accent)', minWidth: '18px' }}
                      >
                        {progress}%
                      </span>
                    )}
                  </>
                ) : (
                  <Camera size={18} color="var(--text-secondary)" />
                )}
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handlePhotoUpload}
                className="hidden"
              />

              {/* 中：文本输入框 */}
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入你的饮食问题..."
                className="flex-1 h-11 px-4 rounded-full text-sm"
                disabled={isStreaming}
              />

              {/* 右：蓝色圆形发送按钮 */}
              <button
                onClick={handleSend}
                disabled={!input.trim() || isStreaming}
                aria-label="发送"
                className="w-11 h-11 rounded-full flex items-center justify-center disabled:opacity-30 transition-all active:scale-90 btn-primary"
              >
                {isStreaming ? (
                  <Spinner size={18} color="white" className="animate-spin" />
                ) : (
                  <PaperPlaneTilt size={18} weight="fill" color="white" />
                )}
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
