'use client';
import { useWorkbench } from '../hooks/useWorkbench';
import { WorkbenchContext } from '../store/WorkbenchContext';
import { ResearchShell } from '../components/ResearchShell';

/** Only the application composition belongs at route level. */
export default function Home() {
  const workbench = useWorkbench();
  return (
    <WorkbenchContext.Provider value={workbench}>
      <ResearchShell />
    </WorkbenchContext.Provider>
  );
}
