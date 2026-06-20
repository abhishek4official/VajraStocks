import { AgentSidebar } from './AgentSidebar';
import { ConversationThread } from './ConversationThread';
import { ContextPanel } from './ContextPanel';

export function AIResearch() {
  return (
    <div className="flex-1 flex overflow-hidden bg-[#07080a]">
      <AgentSidebar />
      <main className="flex-1 flex flex-col min-w-0">
        <ConversationThread />
      </main>
      <ContextPanel />
    </div>
  );
}
