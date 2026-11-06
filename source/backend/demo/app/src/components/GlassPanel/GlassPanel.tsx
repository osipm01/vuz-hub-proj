import { useEffect, useRef, useState, type ReactNode } from 'react';
import NavPath from './NavPath';
import './GlassPanel.css';



interface GlassPanelProps {
  title?: string;
  /** Слот header — если передан, заменяет заголовок */
  header?: ReactNode;
  children?: ReactNode;
  /** Показывать ли анимацию появления при монтировании (аналог `appear`) */
  appear?: boolean;
}

export default function GlassPanel({
  title,
  header,
  children,
  appear = true,
}: GlassPanelProps) {
  // `mounted` управляет появлением: стартуем с "enter-from", затем переключаем
  const [mounted, setMounted] = useState(!appear);
  const [visible, setVisible] = useState(!appear);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!appear) return;
    // Двойной rAF, чтобы браузер успел отрисовать стартовое состояние
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = requestAnimationFrame(() => setVisible(true));
    });
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [appear]);

  useEffect(() => {
    if (visible) setMounted(true);
  }, [visible]);

  const showHeader = Boolean(title || header);

  return (
    <div
      className={[
        'glass-panel',
        'slide-fade-enter-active',
        visible ? 'slide-fade-enter-to' : 'slide-fade-enter-from',
        mounted ? 'is-mounted' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {showHeader && (
        <header className="panel-header">
          {header ?? <h3>{title}</h3>}
        </header>
      )}

      <NavPath />

      <div className="panel-content">{children}</div>
    </div>
  );
}
