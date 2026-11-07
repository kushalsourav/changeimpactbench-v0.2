'use client';
import { createContext, useContext } from 'react';
import type { useWorkbench } from '../hooks/useWorkbench';

export type WorkbenchState = ReturnType<typeof useWorkbench>;
export const WorkbenchContext = createContext<WorkbenchState | null>(null);
export function useWorkbenchState(): WorkbenchState {
  const state = useContext(WorkbenchContext);
  if (!state) throw new Error('WorkbenchProvider is missing');
  return state;
}
