import { useState, useRef } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { Camera, X, Spinner, Check } from '@phosphor-icons/react';
import { usePhotoRecognition } from '../hooks/usePhotoRecognition';
import { useUiStore } from '../stores/uiStore';
import { useMealStore } from '../stores/mealStore';
import { CATEGORY_META, MEAL_SLOTS } from '../data/foods';
import toast from 'react-hot-toast';

// 餐次选择列表（提到组件外，避免每次 render 重建）
const MEAL_OPTIONS = MEAL_SLOTS.map(s => ({ key: s.key, label: s.label }));

export default function PhotoRecognition() {
  const { showPhotoModal, closePhotoModal } = useUiStore();
  const addFood = useMealStore(s => s.addFood);
  const { isRecognizing, progress, result, startRecognize, cancel, reset } = usePhotoRecognition();
  const reduce = useReducedMotion();
  const [selectedMeal, setSelectedMeal] = useState('lunch');
  const fileRef = useRef(null);

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = ''; // 重置以便重复选择同一文件
    reset();
    await startRecognize(file);
  };

  const handleAddToMeal = () => {
    if (!result?.dish) return;
    const d = result.dish;
    const food = {
      name: d.name || '未知菜品',
      category: d.category || '未知',
      unit: '份',
      kcal: d.kcal || 0,
      protein: d.protein || 0,
      carb: d.carb || 0,
      fat: d.fat || 0,
    };
    addFood(selectedMeal, food);
    const label = MEAL_OPTIONS.find(m => m.key === selectedMeal)?.label || selectedMeal;
    toast.success(`已添加到${label}`);
    reset();
    closePhotoModal();
  };

  // 关闭弹窗：先 cancel 释放 in-flight 请求，再清状态
  const handleClose = () => {
    cancel();
    reset();
    closePhotoModal();
  };

  return (
    <AnimatePresence>
      {showPhotoModal && (
        <>
          <motion.div
            className="fixed inset-0 overlay-backdrop z-50"
            initial={reduce ? false : { opacity: 0 }}
            animate={reduce ? false : { opacity: 1 }}
            exit={reduce ? false : { opacity: 0 }}
            onClick={handleClose}
          />
          <motion.div
            className="fixed inset-x-4 top-1/2 -translate-y-1/2 z-50 max-w-sm mx-auto"
            initial={reduce ? false : { opacity: 0, scale: 0.95 }}
            animate={reduce ? false : { opacity: 1, scale: 1 }}
            exit={reduce ? false : { opacity: 0, scale: 0.95 }}
          >
            <div className="card-strong rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">拍照识菜</h3>
                <button
                  onClick={handleClose}
                  className="w-8 h-8 flex items-center justify-center rounded-full transition-colors"
                  style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
                >
                  <X size={18} />
                </button>
              </div>

              {/* Idle state */}
              {!isRecognizing && !result && (
                <div className="space-y-3">
                  <button
                    onClick={() => fileRef.current?.click()}
                    className="w-full py-12 rounded-xl flex flex-col items-center gap-3 transition-all"
                    style={{
                      border: '2px dashed var(--border-color)',
                      background: 'var(--bg-tertiary)',
                    }}
                  >
                    <div
                      style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '14px',
                        background: 'var(--accent-soft)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Camera size={24} color="var(--accent)" />
                    </div>
                    <span className="text-xs text-[var(--text-tertiary)]">拍照或选择图片</span>
                  </button>
                  <input ref={fileRef} type="file" accept="image/*" capture="environment" onChange={handleFile} className="hidden" />
                </div>
              )}

              {/* Recognizing */}
              {isRecognizing && (
                <div className="flex flex-col items-center py-8 gap-5">
                  <Spinner size={36} className="animate-spin" style={{ color: 'var(--accent)' }} />
                  <p className="text-sm text-[var(--text-secondary)] font-medium">AI 正在识别中...</p>
                  <p className="text-[11px] text-[var(--text-tertiary)]">分析食材、推荐搭配、计算营养</p>
                </div>
              )}

              {/* Result */}
              {result && (
                <div className="space-y-3">
                  {/* 识别到的食材 */}
                  {result.ingredients && result.ingredients.length > 0 && (
                    <div>
                      <p className="text-[10px] text-[var(--text-tertiary)] mb-2">识别到的食材</p>
                      <div className="flex flex-wrap gap-1.5">
                        {result.ingredients.map((ing, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium"
                            style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
                          >
                            {ing.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 推荐菜品卡片 */}
                  <div
                    className="p-3.5 rounded-xl"
                    style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0"
                        style={{ background: CATEGORY_META[result.dish?.category]?.color || 'var(--bg-tertiary)' }}
                      >
                        {CATEGORY_META[result.dish?.category]?.emoji || '🍽️'}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-[var(--text-primary)]">
                          {result.dish?.name || '未知菜品'}
                        </p>
                        <p className="text-[10px] text-[var(--text-tertiary)]">
                          {result.dish?.category} · {result.dish?.kcal || 0}kcal
                        </p>
                      </div>
                      <Check size={20} weight="bold" color="var(--success)" />
                    </div>

                    {/* 营养信息 */}
                    <div className="grid grid-cols-4 gap-2 mb-3">
                      {[
                        { label: '热量', value: result.dish?.kcal, unit: 'kcal' },
                        { label: '蛋白质', value: result.dish?.protein, unit: 'g' },
                        { label: '碳水', value: result.dish?.carb, unit: 'g' },
                        { label: '脂肪', value: result.dish?.fat, unit: 'g' },
                      ].map(n => (
                        <div key={n.label} className="text-center">
                          <p className="font-number text-sm font-semibold text-[var(--text-primary)]">
                            {n.value || 0}
                          </p>
                          <p className="text-[9px] text-[var(--text-tertiary)]">{n.unit} {n.label}</p>
                        </div>
                      ))}
                    </div>

                    {/* 推荐理由 */}
                    {result.dish?.reason && (
                      <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                        💡 {result.dish.reason}
                      </p>
                    )}
                  </div>

                  {/* 搭配建议 */}
                  {result.pairing?.tip && (
                    <div
                      className="p-3 rounded-xl"
                      style={{ background: 'rgba(99, 102, 241, 0.06)', border: '1px solid rgba(99, 102, 241, 0.12)' }}
                    >
                      <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                        🥗 {result.pairing.tip}
                      </p>
                      {result.pairing.recommend_pair && result.pairing.recommend_pair.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {result.pairing.recommend_pair.map((name, i) => (
                            <span
                              key={i}
                              className="text-[10px] px-2 py-0.5 rounded-md"
                              style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}
                            >
                              + {name}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Meal selector */}
                  <div>
                    <p className="text-xs text-[var(--text-tertiary)] mb-2.5">添加到：</p>
                    <div className="flex gap-2">
                      {MEAL_OPTIONS.map(m => (
                        <button
                          key={m.key}
                          onClick={() => setSelectedMeal(m.key)}
                          className={`flex-1 py-2.5 rounded-xl text-xs font-medium transition-all ${
                            selectedMeal === m.key
                              ? 'text-white'
                              : 'text-[var(--text-secondary)]'
                          }`}
                          style={selectedMeal === m.key
                            ? { background: 'var(--accent)' }
                            : { background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }
                          }
                        >
                          {m.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={handleAddToMeal}
                    className="w-full py-3 rounded-2xl text-white text-sm font-semibold btn-primary"
                  >
                    确认添加
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
