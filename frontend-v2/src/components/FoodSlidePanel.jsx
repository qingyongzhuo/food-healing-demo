import { useState, useMemo } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { X, MagnifyingGlass, Plus, Check, PencilSimple } from '@phosphor-icons/react';
import { FOODS_DATA, CATEGORIES, CATEGORY_META, CAT_TEXT_VAR } from '../data/foods';
import { useMealStore } from '../stores/mealStore';
import { useUiStore } from '../stores/uiStore';
import toast from 'react-hot-toast';

const MEAL_LABEL = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' };

// 分类标签文字色（沿用 FoodTag 模式，与 CSS 变量对齐）
export default function FoodSlidePanel() {
  const { showSlidePanel, activeMeal, closeSlidePanel } = useUiStore();
  const addFood = useMealStore(s => s.addFood);
  const meals = useMealStore(s => s.meals);
  const history = useMealStore(s => s.history);
  const reduce = useReducedMotion();

  const [search, setSearch] = useState('');
  const [filterCat, setFilterCat] = useState('全部');
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [showCustom, setShowCustom] = useState(false);
  const [custom, setCustom] = useState({ name: '', weight: '', kcal: '', protein: '', carb: '', fat: '' });

  // 常吃食材：从历史 + 当日统计 top 8，不足则 fallback 到默认推荐
  const frequentFoods = useMemo(() => {
    const counter = new Map();
    const allRecords = [
      ...Object.values(history || {}).flatMap(d => Object.values(d).flat()),
      ...Object.values(meals).flat(),
    ];
    allRecords.forEach(f => {
      if (f?.id && !String(f.id).startsWith('custom_')) {
        counter.set(f.id, (counter.get(f.id) || 0) + 1);
      }
    });
    const sorted = [...counter.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([id]) => FOODS_DATA.find(f => f.id === id))
      .filter(Boolean);
    return (sorted.length >= 4 ? sorted : FOODS_DATA.slice(0, 8)).slice(0, 8);
  }, [history, meals]);

  const results = useMemo(() => {
    let list = FOODS_DATA;
    if (filterCat !== '全部') list = list.filter(f => f.category === filterCat);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(f => f.name.toLowerCase().includes(q));
    }
    return list;
  }, [search, filterCat]);

  const toggleSelect = (food) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(food.id)) next.delete(food.id);
      else next.add(food.id);
      return next;
    });
  };

  // 常吃食材一键直接添加（不走多选，规范要求"点击一键快速选中添加"）
  const quickAdd = (food) => {
    addFood(activeMeal, food);
    toast.success(`已添加 ${food.name}`);
  };

  const handleConfirm = () => {
    if (selectedIds.size === 0) {
      toast('请先选择食材');
      return;
    }
    const foods = FOODS_DATA.filter(f => selectedIds.has(f.id));
    foods.forEach(f => addFood(activeMeal, f));
    toast.success(`已添加 ${foods.length} 种食材至${MEAL_LABEL[activeMeal] || '餐食'}`);
    handleClose();
  };

  const handleCustomSave = () => {
    if (!custom.name.trim()) {
      toast('请填写食物名称');
      return;
    }
    const food = {
      id: 'custom_' + Date.now(),
      name: custom.name.trim(),
      category: '自定义',
      unit: custom.weight ? `份(${custom.weight}g)` : '份',
      kcal: parseInt(custom.kcal) || 0,
      protein: parseFloat(custom.protein) || 0,
      carb: parseFloat(custom.carb) || 0,
      fat: parseFloat(custom.fat) || 0,
    };
    addFood(activeMeal, food);
    toast.success(`已添加 ${food.name}`);
    setCustom({ name: '', weight: '', kcal: '', protein: '', carb: '', fat: '' });
    setShowCustom(false);
  };

  const handleClose = () => {
    setSearch('');
    setFilterCat('全部');
    setSelectedIds(new Set());
    setShowCustom(false);
    setCustom({ name: '', weight: '', kcal: '', protein: '', carb: '', fat: '' });
    closeSlidePanel();
  };

  return (
    <AnimatePresence>
      {showSlidePanel && (
        <>
          {/* 浅遮罩 — 不黑屏，底层首页轻微透出 */}
          <motion.div
            className="fixed inset-0 z-40"
            style={{ background: 'rgba(0, 0, 0, 0.15)', backdropFilter: 'blur(2px)', WebkitBackdropFilter: 'blur(2px)' }}
            initial={reduce ? false : { opacity: 0 }}
            animate={reduce ? false : { opacity: 1 }}
            exit={reduce ? false : { opacity: 0 }}
            onClick={handleClose}
          />
          <motion.div
            className="fixed bottom-0 left-0 right-0 z-50 mx-auto max-w-lg flex flex-col rounded-t-[28px] overflow-hidden glass-overlay"
            style={{
              boxShadow: '0 -8px 32px rgba(0, 0, 0, 0.08)',
              maxHeight: '88vh',
            }}
            initial={reduce ? false : { y: '100%' }}
            animate={reduce ? false : { y: 0 }}
            exit={reduce ? false : { y: '100%' }}
            transition={reduce ? {} : { type: 'spring', stiffness: 320, damping: 34, mass: 0.8 }}
          >
            {/* Handle */}
            <div className="flex justify-center pt-2.5 pb-1">
              <div className="w-9 h-1 rounded-full" style={{ background: 'var(--border-color)' }} />
            </div>

            {/* 1. 顶部操作栏 */}
            <div className="flex items-center justify-between px-5 py-2 flex-shrink-0">
              <div className="flex items-baseline gap-1.5">
                <h3 className="text-[17px] font-semibold" style={{ color: 'var(--text-primary)' }}>
                  添加食物
                </h3>
                {activeMeal && (
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    · {MEAL_LABEL[activeMeal]}
                  </span>
                )}
              </div>
              <button
                onClick={handleClose}
                className="w-8 h-8 flex items-center justify-center rounded-full transition-colors"
                style={{ background: 'rgba(118, 118, 123, 0.12)', color: 'var(--text-secondary)' }}
                aria-label="关闭"
              >
                <X size={16} weight="bold" />
              </button>
            </div>

            {/* 2. 全局搜索框 */}
            <div className="px-5 pb-2.5 flex-shrink-0">
              <div className="relative">
                <MagnifyingGlass
                  size={16}
                  weight="regular"
                  className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: 'var(--text-tertiary)' }}
                />
                <input
                  type="text"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="搜索食材、菜品、主食"
                  className="w-full h-9 pl-9 pr-3 text-sm rounded-xl outline-none"
                  style={{
                    background: 'rgba(118, 118, 123, 0.08)',
                    color: 'var(--text-primary)',
                    border: '1px solid transparent',
                  }}
                />
              </div>
            </div>

            {/* 3. 横向滚动分类标签栏 */}
            <div className="px-5 py-2 flex gap-2 overflow-x-auto scrollbar-none flex-shrink-0">
              <CatChip label="全部" active={filterCat === '全部'} onClick={() => setFilterCat('全部')} />
              {CATEGORIES.map(cat => (
                <CatChip
                  key={cat}
                  label={cat}
                  color={CATEGORY_META[cat]?.color}
                  active={filterCat === cat}
                  onClick={() => setFilterCat(cat)}
                />
              ))}
            </div>

            {/* 可滚动内容区 */}
            <div className="flex-1 overflow-y-auto scrollbar-none px-5">
              {/* 4. 常吃食材快捷区 */}
              {!search.trim() && filterCat === '全部' && frequentFoods.length > 0 && (
                <div className="pt-1 pb-3">
                  <p className="text-[11px] font-medium mb-2" style={{ color: 'var(--text-tertiary)' }}>
                    我的常吃食材
                  </p>
                  <div className="flex gap-2 overflow-x-auto scrollbar-none -mx-1 px-1 pb-1">
                    {frequentFoods.map(food => (
                      <button
                        key={food.id}
                        onClick={() => quickAdd(food)}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg whitespace-nowrap transition-all active:scale-95"
                        style={{
                          background: 'var(--glass-bg)',
                          border: '1px solid var(--border-color)',
                        }}
                      >
                        <span className="text-sm">{CATEGORY_META[food.category]?.emoji}</span>
                        <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                          {food.name}
                        </span>
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded"
                          style={{
                            background: CATEGORY_META[food.category]?.color || 'var(--cat-staple)',
                            color: CAT_TEXT_VAR[food.category] || 'var(--text-secondary)',
                          }}
                        >
                          {food.category}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* 5. 食物列表 */}
              {results.length === 0 ? (
                <p className="text-center text-sm py-8" style={{ color: 'var(--text-tertiary)' }}>
                  没有找到匹配的食材
                </p>
              ) : (
                <div className="space-y-1.5 pb-3">
                  {results.map(food => {
                    const selected = selectedIds.has(food.id);
                    return (
                      <div
                        key={food.id}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-2xl"
                        style={{
                          background: 'var(--glass-bg)',
                          border: '1px solid var(--border-color)',
                        }}
                      >
                        <span className="text-lg flex-shrink-0">{CATEGORY_META[food.category]?.emoji || '🍽️'}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                              {food.name}
                            </p>
                            <span
                              className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0"
                              style={{
                                background: CATEGORY_META[food.category]?.color || 'var(--cat-staple)',
                                color: CAT_TEXT_VAR[food.category] || 'var(--text-secondary)',
                              }}
                            >
                              {food.category}
                            </span>
                          </div>
                          <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                            {food.kcal} kcal / {food.unit}
                          </p>
                        </div>
                        <button
                          onClick={() => toggleSelect(food)}
                          className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-all active:scale-90"
                          style={
                            selected
                              ? { background: 'var(--success)', color: '#fff' }
                              : { background: 'var(--accent)', color: '#fff' }
                          }
                          aria-label={selected ? '取消选择' : '添加'}
                        >
                          {selected ? <Check size={16} weight="bold" /> : <Plus size={16} weight="bold" />}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* 6. 自定义食物入口 */}
              <div className="pb-3">
                <button
                  onClick={() => setShowCustom(!showCustom)}
                  className="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs transition-colors"
                  style={{
                    background: 'rgba(118, 118, 123, 0.06)',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <PencilSimple size={13} />
                  未找到食材？手动添加自定义食物
                </button>

                <AnimatePresence>
                  {showCustom && (
                    <motion.div
                      className="mt-2 p-3 rounded-2xl space-y-2"
                      style={{ background: 'var(--glass-bg)', border: '1px solid var(--border-color)' }}
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                    >
                      <input
                        type="text"
                        value={custom.name}
                        onChange={e => setCustom({ ...custom, name: e.target.value })}
                        placeholder="食物名称"
                        className="w-full h-9 px-3 text-sm rounded-lg outline-none"
                        style={{ background: 'rgba(118, 118, 123, 0.08)', color: 'var(--text-primary)' }}
                      />
                      <div className="grid grid-cols-2 gap-2">
                        <input
                          type="text"
                          value={custom.weight}
                          onChange={e => setCustom({ ...custom, weight: e.target.value })}
                          placeholder="重量(g)"
                          className="h-9 px-3 text-sm rounded-lg outline-none"
                          style={{ background: 'rgba(118, 118, 123, 0.08)', color: 'var(--text-primary)' }}
                        />
                        <input
                          type="number"
                          value={custom.kcal}
                          onChange={e => setCustom({ ...custom, kcal: e.target.value })}
                          placeholder="热量(kcal)"
                          className="h-9 px-3 text-sm rounded-lg outline-none"
                          style={{ background: 'rgba(118, 118, 123, 0.08)', color: 'var(--text-primary)' }}
                        />
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <input
                          type="number"
                          value={custom.protein}
                          onChange={e => setCustom({ ...custom, protein: e.target.value })}
                          placeholder="蛋白"
                          className="h-9 px-3 text-sm rounded-lg outline-none"
                          style={{ background: 'rgba(118, 118, 123, 0.08)', color: 'var(--text-primary)' }}
                        />
                        <input
                          type="number"
                          value={custom.carb}
                          onChange={e => setCustom({ ...custom, carb: e.target.value })}
                          placeholder="碳水"
                          className="h-9 px-3 text-sm rounded-lg outline-none"
                          style={{ background: 'rgba(118, 118, 123, 0.08)', color: 'var(--text-primary)' }}
                        />
                        <input
                          type="number"
                          value={custom.fat}
                          onChange={e => setCustom({ ...custom, fat: e.target.value })}
                          placeholder="脂肪"
                          className="h-9 px-3 text-sm rounded-lg outline-none"
                          style={{ background: 'rgba(118, 118, 123, 0.08)', color: 'var(--text-primary)' }}
                        />
                      </div>
                      <button
                        onClick={handleCustomSave}
                        disabled={!custom.name.trim()}
                        className="w-full h-9 rounded-xl text-white text-sm font-medium disabled:opacity-40 btn-primary"
                      >
                        保存并添加
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* 7. 底部固定操作栏 */}
            <div
              className="px-5 py-3 flex items-center gap-3"
              style={{
                background: 'var(--glass-bg-strong)',
                borderTop: '1px solid var(--border-color)',
                paddingBottom: 'calc(0.75rem + env(safe-area-inset-bottom))',
              }}
            >
              <span className="text-sm flex-shrink-0" style={{ color: 'var(--text-secondary)' }}>
                已选 <span className="font-number font-semibold" style={{ color: 'var(--text-primary)' }}>{selectedIds.size}</span> 种食材
              </span>
              <button
                onClick={handleConfirm}
                disabled={selectedIds.size === 0}
                className="flex-1 h-10 rounded-xl text-white text-sm font-medium disabled:opacity-40 btn-primary"
              >
                确认添加至{activeMeal ? MEAL_LABEL[activeMeal] : '餐食'}
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function CatChip({ label, color, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 px-3.5 py-2.5 rounded-lg text-[13px] font-medium whitespace-nowrap transition-all active:scale-95"
      style={
        active
          ? { background: 'var(--accent)', color: '#fff' }
          : { background: 'rgba(118, 118, 123, 0.08)', color: 'var(--text-primary)' }
      }
    >
      {color && !active && (
        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
      )}
      {label}
    </button>
  );
}
