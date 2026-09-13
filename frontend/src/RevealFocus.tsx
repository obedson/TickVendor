import { useEffect, useRef, type ReactNode } from 'react';

export function focusRevealed(element: HTMLElement | null) {
  if (!element) return;
  const focus = element.querySelector<HTMLElement>('input:not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled])') || element;
  if (focus === element) element.tabIndex = -1;
  focus.focus({ preventScroll: true });
  const bounds = element.getBoundingClientRect();
  if (bounds.top < 0 || bounds.top > window.innerHeight - 100) element.scrollIntoView({ block: 'start', behavior: 'instant' });
}
export function useRevealFocus(trigger: unknown, selector: string) {
  useEffect(() => { if (trigger) focusRevealed(document.querySelector<HTMLElement>(selector)); }, [trigger, selector]);
}
export function TaskDialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const previous = document.activeElement as HTMLElement | null; ref.current?.showModal(); return () => { ref.current?.close(); previous?.focus(); }; }, []);
  return <dialog ref={ref} className="panel governance-dialog" aria-label={title} onCancel={event => { event.preventDefault(); onClose(); }}>{children}</dialog>;
}
