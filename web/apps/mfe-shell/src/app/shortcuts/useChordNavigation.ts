import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePermissions } from '@mfe/auth';
import { isEditableElement } from './keyboard-utils';
import { CHORD_MAP, CHORD_TIMEOUT_MS, type ChordEntry } from './chord-navigation.config';

/* ------------------------------------------------------------------ */
/*  useChordNavigation — G-chord state machine                         */
/*                                                                     */
/*  States: idle → pending (after "g") → navigate | idle (timeout)     */
/* ------------------------------------------------------------------ */

export interface ChordNavigationState {
  /** True when waiting for second keystroke */
  isPending: boolean;
  /** Permission-filtered chord entries available during pending state */
  activeChords: ChordEntry[];
  /** Cancel pending state */
  cancel: () => void;
}

export function useChordNavigation(): ChordNavigationState {
  const [isPending, setIsPending] = useState(false);
  const navigate = useNavigate();
  const { hasModule } = usePermissions();
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activeChords = useMemo(
    () => CHORD_MAP.filter((c) => !c.permission || hasModule(c.permission)),
    [hasModule],
  );

  const cancel = useCallback(() => {
    setIsPending(false);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      // Ignore if inside editable element or with modifiers
      if (isEditableElement(e.target)) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      const key = e.key.toLowerCase();

      if (!isPending) {
        // First key: "g" activates pending state
        if (key === 'g' && !e.shiftKey) {
          setIsPending(true);
          timeoutRef.current = setTimeout(() => {
            setIsPending(false);
          }, CHORD_TIMEOUT_MS);
        }
        return;
      }

      // Pending state: check for matching chord
      e.preventDefault();
      e.stopImmediatePropagation();

      if (key === 'escape') {
        cancel();
        return;
      }

      const match = activeChords.find((c) => c.key === key);
      if (match) {
        cancel();
        navigate(match.path);
      } else {
        // Unrecognized key — cancel
        cancel();
      }
    };

    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [isPending, activeChords, cancel, navigate]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return { isPending, activeChords, cancel };
}
