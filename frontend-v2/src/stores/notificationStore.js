import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * 通知类型：
 * - type: 'diet'（饮食提醒）| 'ai'（AI 营养推送）
 * - tone: 'positive'（正向绿）| 'warning'（警示橙）
 * - read: boolean
 * - detail: 详情弹窗正文
 */

// 初始 mock 通知（量级小，纯本地）
const INITIAL_NOTIFICATIONS = [
  {
    id: 'n1',
    type: 'diet',
    tone: 'warning',
    title: '午餐未记录',
    body: '已过 13:00，今天的午餐还没记录哦，记得吃完来登记一下～',
    time: '今天 13:05',
    icon: 'alarm',
    read: false,
    detail: '检测到你今天午餐时段（11:00-13:00）尚未添加任何食物记录。规律进餐有助于稳定血糖和代谢，建议尽快补充午餐记录。若已吃过，可点击「拍照识菜」快速登记。',
  },
  {
    id: 'n2',
    type: 'ai',
    tone: 'positive',
    title: '今日营养分析已生成',
    body: '你今天的蛋白质摄入达标 95.3%，距离目标只差一点点，继续加油！',
    time: '今天 12:30',
    icon: 'ai',
    read: false,
    detail: '今日营养摄入概览：\n· 热量 1635 / 2000 kcal（81.8%）\n· 蛋白质 57.2 / 60 g（95.3%）\n· 碳水 218 / 260 g（83.8%）\n· 脂肪 53.5 / 65 g（82.3%）\n\n建议：晚餐可补充一份清蒸鱼（约 25g 蛋白质）即可达成今日蛋白目标。',
  },
  {
    id: 'n3',
    type: 'diet',
    tone: 'warning',
    title: '热量超标提醒',
    body: '昨日总热量 2275 kcal，超出目标 13.8%，注意今天清淡饮食。',
    time: '昨天 21:00',
    icon: 'plate',
    read: true,
    detail: '昨日总摄入 2275 kcal，超出目标 275 kcal。\n超标来源：晚餐红烧肉（435 kcal）+ 加餐薯片（190 kcal）+ 下午奶茶（220 kcal）。\n\n建议：今日尝试以蒸煮为主，减少油炸食品，并增加一份蔬菜。',
  },
  {
    id: 'n4',
    type: 'ai',
    tone: 'positive',
    title: '为你推荐晚餐食谱',
    body: '基于你今天的营养缺口，推荐：清蒸鱼 + 蒜蓉西兰花 + 杂粮饭。',
    time: '昨天 17:30',
    icon: 'ai',
    read: true,
    detail: '推荐晚餐组合（约 620 kcal）：\n· 清蒸鱼 150g - 蛋白 25g，热量 180 kcal\n· 蒜蓉西兰花 150g - 蛋白 5g，热量 80 kcal\n· 杂粮饭 200g - 蛋白 7g，热量 220 kcal\n\n这个搭配可以帮你补齐今天的蛋白质，热量也不会超标。',
  },
  {
    id: 'n5',
    type: 'ai',
    tone: 'positive',
    title: '营养科普：膳食纤维',
    body: '成年人每日建议摄入 25-30g 膳食纤维，多吃全谷物和蔬菜。',
    time: '前天 10:00',
    icon: 'ai',
    read: true,
    detail: '膳食纤维的作用：\n1. 促进肠道蠕动，预防便秘\n2. 延缓糖分吸收，稳定血糖\n3. 增加饱腹感，利于体重管理\n\n推荐食材：燕麦、红薯、西兰花、苹果、豆类。\n建议每日摄入：25-30g（约 3 份蔬菜 + 2 份水果 + 1 份全谷物）。',
  },
];

export const useNotificationStore = create(
  persist(
    (set, get) => ({
      notifications: INITIAL_NOTIFICATIONS,

      getByCategory(category) {
        const list = get().notifications;
        if (category === '全部通知') return list;
        if (category === '饮食提醒') return list.filter(n => n.type === 'diet');
        if (category === 'AI 营养推送') return list.filter(n => n.type === 'ai');
        return list;
      },

      markAsRead(id) {
        set(state => ({
          notifications: state.notifications.map(n =>
            n.id === id ? { ...n, read: true } : n
          ),
        }));
      },

      markAllRead() {
        set(state => ({
          notifications: state.notifications.map(n => ({ ...n, read: true })),
        }));
      },

      removeAll() {
        set({ notifications: [] });
      },

      remove(id) {
        set(state => ({
          notifications: state.notifications.filter(n => n.id !== id),
        }));
      },

      unreadCount() {
        return get().notifications.filter(n => !n.read).length;
      },
    }),
    {
      name: 'food-notifications',
    }
  )
);
