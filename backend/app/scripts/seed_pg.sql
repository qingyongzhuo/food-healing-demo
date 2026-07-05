-- ============================================================
-- PostgreSQL 演示数据 seed 脚本
-- ============================================================
-- 用法（请用你自己的账号 / 主机 / 密码替换占位符）:
--   psql "postgresql://<pg-user>:<pg-password>@<pg-host>:5432/food_healing" -f seed_pg.sql
--
-- 或:
--   set PGPASSWORD=<pg-password>
--   psql -h <pg-host> -p 5432 -U <pg-user> -d food_healing -f seed_pg.sql
--
-- 内容:
--   1. u001 近 7 天 nutrition_log（21 条 = 7 天 × 3 餐）
--      每条含 tray_json（菜盘快照，JSONB 数组）+ nutrition（营养汇总，JSONB）
--   2. 1 条 weekly_reports（本周周报缓存）
--
-- 幂等：先 DELETE u001 的演示数据再插，可重复运行。
-- ============================================================

BEGIN;

-- ===== 清理旧演示数据（幂等）=====
DELETE FROM nutrition_log WHERE user_id = 'u001';
DELETE FROM weekly_reports WHERE user_id = 'u001';

-- ===== nutrition_log：u001 近 7 天三餐 =====
-- tray_json 结构（与 recognize_service.py 输出一致）：
--   [{name, category, unit, kcal, protein, carb, fat}, ...]
-- nutrition 结构（营养汇总）：
--   {kcal, protein, carb, fat}

-- Day 1 (今天 - 6 天)
INSERT INTO nutrition_log (user_id, date, meal, tray_json, nutrition, mode) VALUES
('u001', CURRENT_DATE - 6, 'breakfast',
 '[
   {"name":"馒头","category":"主食","unit":"个(100g)","kcal":220,"protein":7,"carb":45,"fat":1},
   {"name":"豆浆","category":"蛋奶","unit":"杯(300ml)","kcal":60,"protein":5,"carb":6,"fat":2},
   {"name":"水煮蛋","category":"蛋奶","unit":"个(50g)","kcal":70,"protein":6,"carb":0,"fat":5}
 ]'::jsonb,
 '{"kcal":350,"protein":18,"carb":51,"fat":8}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 6, 'lunch',
 '[
   {"name":"白米饭","category":"主食","unit":"份(200g)","kcal":230,"protein":5,"carb":50,"fat":1},
   {"name":"红烧鸡","category":"肉类","unit":"份(150g)","kcal":250,"protein":22,"carb":8,"fat":15},
   {"name":"酸辣土豆丝","category":"蔬菜","unit":"份(150g)","kcal":130,"protein":3,"carb":22,"fat":4},
   {"name":"紫菜蛋花汤","category":"汤品","unit":"碗(300ml)","kcal":50,"protein":4,"carb":3,"fat":2}
 ]'::jsonb,
 '{"kcal":660,"protein":34,"carb":83,"fat":22}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 6, 'dinner',
 '[
   {"name":"杂粮饭","category":"主食","unit":"份(200g)","kcal":220,"protein":7,"carb":46,"fat":1},
   {"name":"清蒸鱼","category":"肉类","unit":"份(150g)","kcal":180,"protein":25,"carb":3,"fat":7},
   {"name":"炒青菜","category":"蔬菜","unit":"份(150g)","kcal":70,"protein":3,"carb":8,"fat":3}
 ]'::jsonb,
 '{"kcal":470,"protein":35,"carb":57,"fat":11}'::jsonb,
 'daily');

-- Day 2
INSERT INTO nutrition_log (user_id, date, meal, tray_json, nutrition, mode) VALUES
('u001', CURRENT_DATE - 5, 'breakfast',
 '[
   {"name":"燕麦粥","category":"主食","unit":"碗(300g)","kcal":150,"protein":5,"carb":28,"fat":2},
   {"name":"煎蛋","category":"蛋奶","unit":"个(60g)","kcal":90,"protein":6,"carb":0,"fat":7},
   {"name":"牛奶","category":"蛋奶","unit":"杯(250ml)","kcal":150,"protein":8,"carb":12,"fat":8}
 ]'::jsonb,
 '{"kcal":390,"protein":19,"carb":40,"fat":17}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 5, 'lunch',
 '[
   {"name":"炒饭","category":"主食","unit":"份(300g)","kcal":480,"protein":10,"carb":70,"fat":15},
   {"name":"宫保鸡丁","category":"肉类","unit":"份(150g)","kcal":260,"protein":18,"carb":12,"fat":15},
   {"name":"蒜蓉西兰花","category":"蔬菜","unit":"份(150g)","kcal":80,"protein":5,"carb":10,"fat":3}
 ]'::jsonb,
 '{"kcal":820,"protein":33,"carb":92,"fat":33}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 5, 'dinner',
 '[
   {"name":"面条","category":"主食","unit":"碗(250g)","kcal":280,"protein":8,"carb":55,"fat":2},
   {"name":"西红柿炒蛋","category":"蔬菜","unit":"份(150g)","kcal":140,"protein":8,"carb":8,"fat":8},
   {"name":"番茄蛋汤","category":"汤品","unit":"碗(300ml)","kcal":60,"protein":4,"carb":5,"fat":2}
 ]'::jsonb,
 '{"kcal":480,"protein":20,"carb":68,"fat":12}'::jsonb,
 'daily');

-- Day 3
INSERT INTO nutrition_log (user_id, date, meal, tray_json, nutrition, mode) VALUES
('u001', CURRENT_DATE - 4, 'breakfast',
 '[
   {"name":"包子(猪肉)","category":"主食","unit":"个(80g)","kcal":180,"protein":6,"carb":28,"fat":5},
   {"name":"豆浆","category":"蛋奶","unit":"杯(300ml)","kcal":60,"protein":5,"carb":6,"fat":2}
 ]'::jsonb,
 '{"kcal":240,"protein":11,"carb":34,"fat":7}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 4, 'lunch',
 '[
   {"name":"白米饭","category":"主食","unit":"份(200g)","kcal":230,"protein":5,"carb":50,"fat":1},
   {"name":"糖醋排骨","category":"肉类","unit":"份(150g)","kcal":320,"protein":20,"carb":18,"fat":18},
   {"name":"麻婆豆腐","category":"蔬菜","unit":"份(200g)","kcal":180,"protein":12,"carb":8,"fat":11},
   {"name":"冬瓜排骨汤","category":"汤品","unit":"碗(300ml)","kcal":90,"protein":6,"carb":4,"fat":6}
 ]'::jsonb,
 '{"kcal":820,"protein":43,"carb":80,"fat":36}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 4, 'dinner',
 '[
   {"name":"红薯","category":"主食","unit":"块(150g)","kcal":130,"protein":2,"carb":30,"fat":0},
   {"name":"鸡胸肉","category":"肉类","unit":"份(100g)","kcal":130,"protein":28,"carb":1,"fat":3},
   {"name":"凉拌黄瓜","category":"蔬菜","unit":"份(100g)","kcal":40,"protein":1,"carb":6,"fat":1}
 ]'::jsonb,
 '{"kcal":300,"protein":31,"carb":37,"fat":4}'::jsonb,
 'daily');

-- Day 4
INSERT INTO nutrition_log (user_id, date, meal, tray_json, nutrition, mode) VALUES
('u001', CURRENT_DATE - 3, 'breakfast',
 '[
   {"name":"花卷","category":"主食","unit":"个(100g)","kcal":210,"protein":6,"carb":42,"fat":2},
   {"name":"蒸蛋","category":"蛋奶","unit":"碗(150g)","kcal":110,"protein":9,"carb":2,"fat":7}
 ]'::jsonb,
 '{"kcal":320,"protein":15,"carb":44,"fat":9}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 3, 'lunch',
 '[
   {"name":"白米饭","category":"主食","unit":"份(200g)","kcal":230,"protein":5,"carb":50,"fat":1},
   {"name":"鱼香肉丝","category":"肉类","unit":"份(150g)","kcal":240,"protein":16,"carb":14,"fat":13},
   {"name":"炒包菜","category":"蔬菜","unit":"份(150g)","kcal":90,"protein":3,"carb":12,"fat":4},
   {"name":"酸辣汤","category":"汤品","unit":"碗(300ml)","kcal":80,"protein":5,"carb":8,"fat":4}
 ]'::jsonb,
 '{"kcal":640,"protein":29,"carb":84,"fat":22}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 3, 'dinner',
 '[
   {"name":"玉米","category":"主食","unit":"根(200g)","kcal":110,"protein":4,"carb":25,"fat":1},
   {"name":"牛肉片","category":"肉类","unit":"份(100g)","kcal":180,"protein":26,"carb":2,"fat":8},
   {"name":"清炒菠菜","category":"蔬菜","unit":"份(150g)","kcal":60,"protein":4,"carb":6,"fat":2}
 ]'::jsonb,
 '{"kcal":350,"protein":34,"carb":33,"fat":11}'::jsonb,
 'daily');

-- Day 5
INSERT INTO nutrition_log (user_id, date, meal, tray_json, nutrition, mode) VALUES
('u001', CURRENT_DATE - 2, 'breakfast',
 '[
   {"name":"燕麦粥","category":"主食","unit":"碗(300g)","kcal":150,"protein":5,"carb":28,"fat":2},
   {"name":"水煮蛋","category":"蛋奶","unit":"个(50g)","kcal":70,"protein":6,"carb":0,"fat":5}
 ]'::jsonb,
 '{"kcal":220,"protein":11,"carb":28,"fat":7}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 2, 'lunch',
 '[
   {"name":"白米饭","category":"主食","unit":"份(200g)","kcal":230,"protein":5,"carb":50,"fat":1},
   {"name":"可乐鸡翅","category":"肉类","unit":"份(150g)","kcal":280,"protein":20,"carb":16,"fat":15},
   {"name":"干煸豆角","category":"蔬菜","unit":"份(150g)","kcal":150,"protein":4,"carb":14,"fat":9},
   {"name":"紫菜蛋花汤","category":"汤品","unit":"碗(300ml)","kcal":50,"protein":4,"carb":3,"fat":2}
 ]'::jsonb,
 '{"kcal":710,"protein":33,"carb":83,"fat":27}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 2, 'dinner',
 '[
   {"name":"杂粮饭","category":"主食","unit":"份(200g)","kcal":220,"protein":7,"carb":46,"fat":1},
   {"name":"水煮肉片","category":"肉类","unit":"份(200g)","kcal":310,"protein":22,"carb":10,"fat":20},
   {"name":"蒜蓉西兰花","category":"蔬菜","unit":"份(150g)","kcal":80,"protein":5,"carb":10,"fat":3}
 ]'::jsonb,
 '{"kcal":610,"protein":34,"carb":66,"fat":24}'::jsonb,
 'daily');

-- Day 6 (昨天)
INSERT INTO nutrition_log (user_id, date, meal, tray_json, nutrition, mode) VALUES
('u001', CURRENT_DATE - 1, 'breakfast',
 '[
   {"name":"馒头","category":"主食","unit":"个(100g)","kcal":220,"protein":7,"carb":45,"fat":1},
   {"name":"牛奶","category":"蛋奶","unit":"杯(250ml)","kcal":150,"protein":8,"carb":12,"fat":8}
 ]'::jsonb,
 '{"kcal":370,"protein":15,"carb":57,"fat":9}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 1, 'lunch',
 '[
   {"name":"白米饭","category":"主食","unit":"份(200g)","kcal":230,"protein":5,"carb":50,"fat":1},
   {"name":"红烧肉","category":"肉类","unit":"份(150g)","kcal":420,"protein":14,"carb":8,"fat":38},
   {"name":"地三鲜","category":"蔬菜","unit":"份(200g)","kcal":200,"protein":5,"carb":28,"fat":8},
   {"name":"番茄蛋汤","category":"汤品","unit":"碗(300ml)","kcal":60,"protein":4,"carb":5,"fat":2}
 ]'::jsonb,
 '{"kcal":910,"protein":28,"carb":91,"fat":49}'::jsonb,
 'daily'),
('u001', CURRENT_DATE - 1, 'dinner',
 '[
   {"name":"面条","category":"主食","unit":"碗(250g)","kcal":280,"protein":8,"carb":55,"fat":2},
   {"name":"西红柿炒蛋","category":"蔬菜","unit":"份(150g)","kcal":140,"protein":8,"carb":8,"fat":8}
 ]'::jsonb,
 '{"kcal":420,"protein":16,"carb":63,"fat":10}'::jsonb,
 'daily');

-- Day 7 (今天)
INSERT INTO nutrition_log (user_id, date, meal, tray_json, nutrition, mode) VALUES
('u001', CURRENT_DATE, 'breakfast',
 '[
   {"name":"花卷","category":"主食","unit":"个(100g)","kcal":210,"protein":6,"carb":42,"fat":2},
   {"name":"豆浆","category":"蛋奶","unit":"杯(300ml)","kcal":60,"protein":5,"carb":6,"fat":2},
   {"name":"水煮蛋","category":"蛋奶","unit":"个(50g)","kcal":70,"protein":6,"carb":0,"fat":5}
 ]'::jsonb,
 '{"kcal":340,"protein":17,"carb":48,"fat":9}'::jsonb,
 'daily'),
('u001', CURRENT_DATE, 'lunch',
 '[
   {"name":"白米饭","category":"主食","unit":"份(200g)","kcal":230,"protein":5,"carb":50,"fat":1},
   {"name":"宫保鸡丁","category":"肉类","unit":"份(150g)","kcal":260,"protein":18,"carb":12,"fat":15},
   {"name":"酸辣土豆丝","category":"蔬菜","unit":"份(150g)","kcal":130,"protein":3,"carb":22,"fat":4},
   {"name":"银耳莲子汤","category":"汤品","unit":"碗(300ml)","kcal":110,"protein":2,"carb":24,"fat":1}
 ]'::jsonb,
 '{"kcal":730,"protein":28,"carb":108,"fat":21}'::jsonb,
 'daily'),
('u001', CURRENT_DATE, 'dinner',
 '[
   {"name":"杂粮饭","category":"主食","unit":"份(200g)","kcal":220,"protein":7,"carb":46,"fat":1},
   {"name":"清蒸鱼","category":"肉类","unit":"份(150g)","kcal":180,"protein":25,"carb":3,"fat":7},
   {"name":"炒青菜","category":"蔬菜","unit":"份(150g)","kcal":70,"protein":3,"carb":8,"fat":3},
   {"name":"紫菜蛋花汤","category":"汤品","unit":"碗(300ml)","kcal":50,"protein":4,"carb":3,"fat":2}
 ]'::jsonb,
 '{"kcal":520,"protein":39,"carb":60,"fat":13}'::jsonb,
 'daily');

-- ===== weekly_reports：u001 本周周报缓存 =====
-- week 格式 YYYYWW（ISO 周数）
-- 数据为近 7 天 nutrition_log 实际汇总：
--   Day1=1480, Day2=1690, Day3=1360, Day4=1310, Day5=1540, Day6=1700, Day7=1590
--   合计 kcal=10670, protein=543, carb=1307, fat=361
INSERT INTO weekly_reports (user_id, week, report_json, generated_at) VALUES
('u001',
 to_char(CURRENT_DATE, 'IYYYIW'),
 '{
   "week_range": "近 7 天",
   "days_logged": 7,
   "total_kcal": 10670,
   "avg_daily_kcal": 1524,
   "kcal_target": 2200,
   "goal_adherence": 0.69,
   "total_protein": 543,
   "avg_daily_protein": 77.6,
   "protein_target": 60,
   "total_carb": 1307,
   "total_fat": 361,
   "highlights": [
     {"date_offset": 1, "meal": "lunch", "kcal": 910, "note": "红烧肉热量超标"},
     {"date_offset": 4, "meal": "lunch", "kcal": 820, "note": "糖醋排骨偏甜"}
   ],
   "suggestions": [
     "本周午餐平均热量偏高，建议晚餐减量",
     "蛋白质摄入达标，保持",
     "建议增加蔬菜摄入量"
   ],
   "ai_summary": "小李本周吃了 7 天食堂，整体营养均衡，但午餐热量略高。阿姨建议多吃蔬菜少吃肥肉哦～"
 }'::jsonb,
 NOW());

COMMIT;

-- ===== 验证查询（可选，输出演示数据）=====
SELECT 'nutrition_log 近 7 天' AS table_name, COUNT(*) AS rows
FROM nutrition_log WHERE user_id = 'u001'
UNION ALL
SELECT 'weekly_reports 本周', COUNT(*)
FROM weekly_reports WHERE user_id = 'u001';

-- 验证 JSONB 可查询（取出今日午餐的菜盘）
SELECT date, meal,
       tray_json->0->>'name' AS first_dish,
       nutrition->>'kcal' AS total_kcal
FROM nutrition_log
WHERE user_id = 'u001' AND date = CURRENT_DATE
ORDER BY meal;
