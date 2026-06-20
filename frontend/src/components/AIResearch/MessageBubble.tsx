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
  
  let currentTable: string[][] = [];
  let currentCodeLines: string[] = [];
  let currentListItems: { text: string; ordered: boolean }[] = [];
  let inCodeBlock = false;

  const flushTable = (key: number) => {
    if (currentTable.length === 0) return;
    if (currentTable.length < 2) {
      currentTable.forEach((row, ri) => {
        elements.push(
          <p key={`tbl-fallback-${key}-${ri}`} className="text-xs leading-relaxed text-slate-400 mb-2">
            {row.join(' | ')}
          </p>
        );
      });
      currentTable = [];
      return;
    }
    const [header, , ...body] = currentTable;
    elements.push(
      <div key={`tbl-${key}`} className="overflow-x-auto my-3">
        <table className="text-[11px] w-full border-collapse">
          <thead>
            <tr>
              {header.map((h, i) => (
                <th key={i} className="text-left px-2 py-1.5 bg-slate-800 border border-slate-700 font-semibold text-slate-300">
                  {h.trim()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((row, ri) => (
              <tr key={ri} className="even:bg-slate-800/30">
                {row.map((cell, ci) => (
                  <td key={ci} className="px-2 py-1.5 border border-slate-700 text-slate-300">
                    {cell.trim()}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    currentTable = [];
  };

  const flushCodeBlock = (key: number) => {
    if (currentCodeLines.length === 0) return;
    elements.push(
      <pre key={`code-${key}`} className="bg-slate-900 border border-slate-800/80 p-3 rounded-lg text-[11px] font-mono text-purple-300 overflow-x-auto my-2.5">
        <code>{currentCodeLines.join('\n')}</code>
      </pre>
    );
    currentCodeLines = [];
  };

  const flushList = (key: number) => {
    if (currentListItems.length === 0) return;
    const isOrdered = currentListItems[0].ordered;
    const listContent = currentListItems.map((item, idx) => {
      const html = parseInlineStyles(item.text);
      return (
        <li key={idx} className="text-xs leading-relaxed text-slate-400 mb-1 ml-4 list-outside" style={{ listStyleType: isOrdered ? 'decimal' : 'disc' }}>
          <span dangerouslySetInnerHTML={{ __html: html }} />
        </li>
      );
    });

    if (isOrdered) {
      elements.push(<ol key={`list-${key}`} className="my-2 pl-4 list-decimal">{listContent}</ol>);
    } else {
      elements.push(<ul key={`list-${key}`} className="my-2 pl-4 list-disc">{listContent}</ul>);
    }
    currentListItems = [];
  };

  const parseInlineStyles = (text: string) => {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-slate-200 font-semibold">$1</strong>')
      .replace(/\*(.+?)\*/g, '<em class="text-slate-300">$1</em>')
      .replace(/`(.+?)`/g, '<code class="bg-slate-800 border border-slate-700 px-1.5 py-0.5 rounded text-[10px] font-mono text-purple-300">$1</code>')
      .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-purple-400 hover:text-purple-300 hover:underline font-medium">$1</a>');
  };

  let elementKey = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // 1. Code block handling
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        inCodeBlock = false;
        flushCodeBlock(elementKey++);
      } else {
        if (currentTable.length > 0) flushTable(elementKey++);
        if (currentListItems.length > 0) flushList(elementKey++);
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      currentCodeLines.push(line);
      continue;
    }

    // 2. Table handling
    if (line.startsWith('|')) {
      if (currentListItems.length > 0) flushList(elementKey++);
      const row = line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      currentTable.push(row);
      continue;
    }
    if (currentTable.length > 0) {
      flushTable(elementKey++);
    }

    // 3. List handling
    const unorderedMatch = line.match(/^(\s*)[-*+]\s+(.*)$/);
    const orderedMatch = line.match(/^(\s*)\d+\.\s+(.*)$/);

    if (unorderedMatch) {
      if (currentTable.length > 0) flushTable(elementKey++);
      currentListItems.push({ text: unorderedMatch[2], ordered: false });
      continue;
    } else if (orderedMatch) {
      if (currentTable.length > 0) flushTable(elementKey++);
      currentListItems.push({ text: orderedMatch[2], ordered: true });
      continue;
    } else if (currentListItems.length > 0) {
      flushList(elementKey++);
    }

    // 4. Headers & empty lines
    if (line.startsWith('### ')) {
      elements.push(<h3 key={elementKey++} className="text-xs font-semibold mt-4 mb-1 text-slate-200">{line.slice(4)}</h3>);
    } else if (line.startsWith('## ')) {
      elements.push(<h2 key={elementKey++} className="text-sm font-bold mt-5 mb-2 text-slate-100 border-b border-slate-800/40 pb-1">{line.slice(3)}</h2>);
    } else if (line.startsWith('# ')) {
      elements.push(<h1 key={elementKey++} className="text-base font-bold mt-6 mb-3 text-purple-400">{line.slice(2)}</h1>);
    } else if (line.trim() === '') {
      elements.push(<div key={elementKey++} className="h-2.5" />);
    } else {
      const html = parseInlineStyles(line);
      elements.push(
        <p
          key={elementKey++}
          className="text-xs leading-relaxed text-slate-400 mb-2"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      );
    }
  }

  // Flush remaining elements
  if (currentTable.length > 0) flushTable(elementKey++);
  if (currentListItems.length > 0) flushList(elementKey++);
  if (currentCodeLines.length > 0) flushCodeBlock(elementKey++);

  return <div className="space-y-1">{elements}</div>;
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
