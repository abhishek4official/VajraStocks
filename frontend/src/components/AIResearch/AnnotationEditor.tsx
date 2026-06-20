import { useState } from 'react';
import { StickyNote, Check, X } from 'lucide-react';
import { useConversationStore } from '../../store/useConversationStore';

interface Props {
  messageId: number;
  currentAnnotation: string | null;
}

export function AnnotationEditor({ messageId, currentAnnotation }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(currentAnnotation ?? '');
  const { addAnnotation } = useConversationStore();

  const save = async () => {
    await addAnnotation(messageId, draft);
    setEditing(false);
  };

  const cancel = () => {
    setDraft(currentAnnotation ?? '');
    setEditing(false);
  };

  if (!editing) {
    return (
      <div className="mt-2">
        {currentAnnotation ? (
          <div
            onClick={() => setEditing(true)}
            className="flex items-start gap-1.5 cursor-pointer group rounded px-2 py-1.5 bg-amber-950/20 border border-amber-900/40"
          >
            <StickyNote size={11} className="text-amber-500 mt-0.5 shrink-0" />
            <span className="text-[11px] text-amber-400 group-hover:underline">{currentAnnotation}</span>
          </div>
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="text-[10px] text-slate-600 hover:text-amber-500 flex items-center gap-1 transition-colors"
          >
            <StickyNote size={10} /> Add note
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="mt-2">
      <textarea
        autoFocus
        rows={2}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="Add a note to this message..."
        className="w-full text-[11px] border border-amber-900/50 rounded px-2 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-amber-600/40 bg-amber-950/20 text-amber-300 placeholder-amber-900/60"
      />
      <div className="flex gap-1.5 mt-1">
        <button
          onClick={save}
          className="flex items-center gap-1 text-[10px] text-white bg-amber-600 hover:bg-amber-700 px-2 py-0.5 rounded transition-colors"
        >
          <Check size={10} /> Save
        </button>
        <button
          onClick={cancel}
          className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 px-2 py-0.5 rounded transition-colors"
        >
          <X size={10} /> Cancel
        </button>
      </div>
    </div>
  );
}
