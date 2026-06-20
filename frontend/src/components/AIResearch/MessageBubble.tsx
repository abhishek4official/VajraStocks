import React from 'react';
import { Bot, User } from 'lucide-react';
import type { ConversationMessage } from '../../store/useConversationStore';
import { AnnotationEditor } from './AnnotationEditor';

const REC_COLORS: Record<string, string> = {
  BULLISH: 'bg-emerald-950/50 text-emerald-400 border-emerald-900/50',
  BEARISH: 'bg-rose-950/50 text-rose-400 border-rose-900/50',
  NEUTRAL: 'bg-slate-800 text-slate-300 border-slate-700',
  AVOID:   'bg-orange-950/50 text-orange-400 border-orange-900/50',
};

function ReportContent({ markdown }: { markdown: string }) {
  const lines = markdown.split('\n');
  const elements: React.ReactNode[] = [];
  let inTable = false;
  let tableRows: string[][] = [];
  let tableKey = 0;

  const flushTable = () => {
    if (tableRows.length < 2) return;
    const [header, , ...body] = tableRows;
    elements.push(
      <div key={`tbl-${tableKey++}`} className="overflow-x-auto my-3">
        <table className="text-[11px] w-full border-collapse">
          <thead>
            <tr>
              {header.map((h, i) => (
                <th key={i} className="text-left px-2 py-1 bg-slate-800 border border-slate-700 font-semibold text-slate-300">
                  {h.trim()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((row, ri) => (
              <tr key={ri} className="even:bg-slate-800/30">
                {row.map((cell, ci) => (
                  <td key={ci} className="px-2 py-1 border border-slate-700 text-slate-300">
                    {cell.trim()}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableRows = [];
    inTable = false;
  };

  lines.forEach((line, i) => {
    if (line.startsWith('|')) {
      inTable = true;
      tableRows.push(line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1));
      return;
    }
    if (inTable) flushTable();

    if (line.startsWith('### '))
      elements.push(<h3 key={i} className="text-xs font-semibold mt-3 mb-1 text-slate-200">{line.slice(4)}</h3>);
    else if (line.startsWith('## '))
      elements.push(<h2 key={i} className="text-sm font-bold mt-4 mb-1.5 text-slate-100">{line.slice(3)}</h2>);
    else if (line.startsWith('# '))
      elements.push(<h1 key={i} className="text-base font-bold mt-4 mb-2 text-purple-400">{line.slice(2)}</h1>);
    else if (line.startsWith('```'))
      elements.push(null);
    else if (line.trim() === '')
      elements.push(<div key={i} className="h-2" />);
    else {
      const html = line
        .replace(/\*\*(.+?)\*\*/g, '<strong class="text-slate-200 font-semibold">$1</strong>')
        .replace(/\*(.+?)\*/g, '<em class="text-slate-300">$1</em>')
        .replace(/`(.+?)`/g, '<code class="bg-slate-800 border border-slate-700 px-1 rounded text-[10px] font-mono text-purple-300">$1</code>');
      elements.push(
        <p
          key={i}
          className="text-xs leading-relaxed text-slate-400"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      );
    }
  });

  if (inTable) flushTable();
  return <div>{elements}</div>;
}

export function MessageBubble({ message }: { message: ConversationMessage }) {
  const isUser = message.role === 'user';
  const time = new Date(message.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[80%]">
          <div className="bg-purple-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm">
            {message.content}
          </div>
          <p className="text-[10px] text-slate-600 text-right mt-1">{time}</p>
        </div>
        <div className="ml-2 mt-1 shrink-0 w-6 h-6 rounded-full bg-purple-900/40 border border-purple-800/40 flex items-center justify-center">
          <User size={12} className="text-purple-400" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex mb-4 gap-2">
      <div className="shrink-0 w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center mt-1">
        <Bot size={12} className="text-slate-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="bg-[#121620] border border-slate-800 rounded-2xl rounded-tl-sm px-4 py-3">
          {message.recommendation && (
            <div className="mb-2">
              <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full border ${REC_COLORS[message.recommendation] ?? REC_COLORS.NEUTRAL}`}>
                {message.recommendation}
                {message.confidence && (
                  <span className="font-normal opacity-70">· {message.confidence}</span>
                )}
              </span>
            </div>
          )}
          <ReportContent markdown={message.content} />
        </div>
        <p className="text-[10px] text-slate-600 mt-1 ml-1">{time}</p>
        <AnnotationEditor messageId={message.id} currentAnnotation={message.annotation} />
      </div>
    </div>
  );
}
