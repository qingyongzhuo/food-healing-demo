/**
 * Card — iOS 扁平卡片组件
 * 白底 + 细边框 + 微阴影
 */
export default function GlassCard({
  children,
  className = '',
  strong = false,
  onClick,
  style,
}) {
  const baseClass = strong ? 'card-strong' : 'card';
  return (
    <div
      className={`${baseClass} ${className}`}
      onClick={onClick}
      style={style}
    >
      {children}
    </div>
  );
}
