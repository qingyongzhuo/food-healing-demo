/**
 * 计算 meals 对象的总营养
 * @param {{ breakfast: Array, lunch: Array, dinner: Array, snack: Array }} meals
 * @returns {{ kcal: number, protein: number, carb: number, fat: number }}
 */
export function calcNutrition(meals) {
  const result = { kcal: 0, protein: 0, carb: 0, fat: 0 };
  if (!meals) return result;
  Object.values(meals).forEach(mealFoods => {
    if (!Array.isArray(mealFoods)) return;
    mealFoods.forEach(f => {
      result.kcal += f.kcal || 0;
      result.protein += f.protein || 0;
      result.carb += f.carb || 0;
      result.fat += f.fat || 0;
    });
  });
  return result;
}

/**
 * 获取营养进度条颜色
 */
export function getBarColor(ratio) {
  if (ratio >= 0.9 && ratio <= 1.1) return 'var(--success)';
  if (ratio > 1.1) return 'var(--danger)';
  return 'var(--text-tertiary)';
}

/**
 * 基于今日饮食生成 AI 营养师摘要
 */
export function generateAiSummary(meals, target) {
  const nutrition = calcNutrition(meals);
  const totalFoods = Object.values(meals).flat().length;
  const kcalRatio = target.kcal > 0 ? nutrition.kcal / target.kcal : 0;

  if (totalFoods === 0) {
    return '今天还没记录饮食哦～点击任意餐次开始记录，我来帮你把控营养。';
  }

  // 检查各类别覆盖
  const allFoods = Object.values(meals).flat();
  const categories = new Set(allFoods.map(f => f.category));
  const missingCategories = [];
  if (!categories.has('蔬菜')) missingCategories.push('蔬菜');
  if (!categories.has('肉类') && !categories.has('蛋奶')) missingCategories.push('蛋白质');

  if (missingCategories.length > 0) {
    return `已记录 ${Math.round(nutrition.kcal)}kcal，但还缺${missingCategories.join('和')}。建议下一餐补上～`;
  }

  if (kcalRatio < 0.7) {
    return `目前 ${Math.round(nutrition.kcal)}kcal，离目标还差 ${Math.round(target.kcal - nutrition.kcal)}kcal。可以再加一份主食或肉类。`;
  }

  if (kcalRatio >= 0.9 && kcalRatio <= 1.1) {
    return `营养达标，搭配均衡！${Math.round(nutrition.kcal)}kcal，蛋白质 ${Math.round(nutrition.protein)}g，今天表现很棒。`;
  }

  if (kcalRatio > 1.1) {
    return `今日已摄入 ${Math.round(nutrition.kcal)}kcal，超出目标 ${Math.round(nutrition.kcal - target.kcal)}kcal。后面可以清淡一点～`;
  }

  return `已记录 ${Math.round(nutrition.kcal)}kcal，继续加油，离目标还有 ${Math.round(target.kcal - nutrition.kcal)}kcal。`;
}