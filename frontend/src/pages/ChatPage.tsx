import { AnimatePresence, motion } from 'framer-motion';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  completeTask,
  completeTraining,
  executeConfirmedAction,
  fetchAssignments,
  fetchDemoEmployees,
  fetchDocuments,
  fetchEquipment,
  fetchOnboardingStatus,
  fetchPayroll,
  fetchTrainings,
  setAuthToken,
  resetOnboarding,
  signEmployeeDocument,
  streamChat,
  submitPayroll,
  updatePersona,
} from '../api';
import type {
  ActionProposal,
  AgentEvent,
  ChatMessage,
  DemoEmployee,
  EmployeeAssignment,
  EmployeeDocument,
  EquipmentItem,
  ExecutionTrace,
  OnboardingStatus,
  PayrollProfile,
  TrainingAssignment,
} from '../api';
import ChatMarkdown from '../components/ChatMarkdown';
import { useTheme } from '../ThemeContext';

// ─── Icons ────────────────────────────────────────────────────────────────────

function SunIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 2 11 13M22 2 15 22 11 13 2 9l20-7z" />
    </svg>
  );
}

function CheckIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function ToolIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  );
}

function ArrowRightIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14M12 5l7 7-7 7" />
    </svg>
  );
}

function ShieldCheckIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

// ─── Sub-components ────────────────────────────────────────────────────────────

function ThinkingDots() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      className="flex items-center gap-1 px-4 py-3"
    >
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="block w-1.5 h-1.5 rounded-full bg-zinc-400 dark:bg-zinc-500"
          animate={{ y: [0, -5, 0] }}
          transition={{ repeat: Infinity, duration: 0.9, delay: i * 0.18, ease: 'easeInOut' }}
        />
      ))}
    </motion.div>
  );
}

function ToolCallBadge({ name }: { name: string }) {
  const label = name.replace(/_tool$/, '').replace(/_/g, ' ');
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium
        bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400 border border-amber-200/60 dark:border-amber-800/50"
    >
      <ToolIcon />
      {label}
    </motion.span>
  );
}

function CitationChip({ text }: { text: string }) {
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      className="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium
        bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400 border border-violet-200/60 dark:border-violet-800/50"
    >
      {text}
    </motion.span>
  );
}

function StreamingText({ text, active }: { text: string; active: boolean }) {
  const [displayed, setDisplayed] = useState('');

  useEffect(() => {
    if (!active) {
      setDisplayed(text);
      return;
    }
    if (displayed.length >= text.length) return;
    const timer = setTimeout(() => {
      setDisplayed(text.slice(0, displayed.length + 3));
    }, 12);
    return () => clearTimeout(timer);
  }, [text, displayed, active]);

  return (
    <span className={active && displayed.length < text.length ? 'streaming-cursor' : ''}>
      <ChatMarkdown content={displayed} />
    </span>
  );
}

// ─── Agent Flow Panel ──────────────────────────────────────────────────────────

const STATUS_DOT: Record<string, string> = {
  started: 'bg-zinc-400 dark:bg-zinc-500',
  completed: 'bg-emerald-500',
  tool: 'bg-amber-500',
  blocked: 'bg-rose-500',
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  started: <ArrowRightIcon />,
  completed: <CheckIcon size={10} />,
  tool: <ToolIcon />,
  blocked: <ShieldCheckIcon size={10} />,
};

function AgentFlowPanel({ entries }: { entries: AgentEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  if (entries.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="overflow-hidden"
    >
      <div className="px-4 pt-3 pb-2 border-t border-zinc-200 dark:border-zinc-800">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 dark:text-zinc-600 mb-2">
          Multi-Agent Orchestration Flow
        </p>
        <div className="space-y-0 max-h-36 overflow-y-auto">
          {entries.map((entry, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="flex items-start gap-2.5 relative"
            >
              {i < entries.length - 1 && (
                <div className="absolute left-[7px] top-[18px] w-px h-full bg-zinc-200 dark:bg-zinc-800" />
              )}
              <div className={`relative z-10 mt-1 shrink-0 w-3.5 h-3.5 rounded-full flex items-center justify-center text-white ${STATUS_DOT[entry.status] ?? 'bg-zinc-300'}`}>
                {entry.status === 'started' && (
                  <motion.div
                    className="absolute inset-0 rounded-full bg-zinc-400 dark:bg-zinc-500"
                    animate={{ scale: [1, 1.6, 1], opacity: [0.5, 0, 0.5] }}
                    transition={{ repeat: Infinity, duration: 1.5 }}
                  />
                )}
                <span className="relative z-10 text-white">
                  {STATUS_ICON[entry.status]}
                </span>
              </div>
              <div className="pb-2.5 min-w-0">
                <p className="text-xs leading-tight font-mono">
                  <span className="font-semibold text-zinc-700 dark:text-zinc-300">
                    {entry.agent.charAt(0).toUpperCase() + entry.agent.slice(1)}
                  </span>
                  <span className="text-zinc-400 dark:text-zinc-600"> · </span>
                  <span className="text-zinc-500 dark:text-zinc-400 break-words">
                    {entry.detail}
                  </span>
                </p>
              </div>
            </motion.div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
    </motion.div>
  );
}

// ─── Phase 3 & 4: HITL Cards & Trace Drawer ──────────────────────────────────

function ActionProposalCard({
  proposal,
  employeeId,
  onConfirmed,
}: {
  proposal: ActionProposal;
  employeeId?: string;
  onConfirmed?: () => void;
}) {
  const [status, setStatus] = useState<'pending' | 'submitting' | 'confirmed' | 'dismissed'>('pending');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (status === 'dismissed') return null;

  const handleApprove = async () => {
    if (!employeeId) return;
    try {
      setStatus('submitting');
      await executeConfirmedAction(employeeId, proposal.action_type, proposal.details);
      setStatus('confirmed');
      onConfirmed?.();
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Execution failed');
      setStatus('pending');
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-3 p-3.5 rounded-xl border border-violet-200 dark:border-violet-900/60 bg-violet-50/70 dark:bg-violet-950/30 text-xs text-left"
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="font-semibold text-violet-900 dark:text-violet-200 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-violet-500 animate-pulse" />
          {proposal.title}
        </span>
        {status === 'confirmed' ? (
          <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 font-medium">
            Confirmed & Submitted
          </span>
        ) : (
          <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 font-medium text-[10px]">
            Requires Human Approval
          </span>
        )}
      </div>

      <div className="space-y-1 text-zinc-600 dark:text-zinc-400 mb-3 bg-white/60 dark:bg-zinc-900/40 p-2 rounded-lg font-mono text-[11px]">
        {Object.entries(proposal.details).map(([k, v]) => (
          <div key={k} className="flex justify-between">
            <span className="text-zinc-400 dark:text-zinc-500">{k}:</span>
            <span className="text-zinc-800 dark:text-zinc-200 font-medium">{String(v)}</span>
          </div>
        ))}
      </div>

      {errorMsg && (
        <p className="text-red-500 text-[11px] mb-2">{errorMsg}</p>
      )}

      {status !== 'confirmed' && (
        <div className="flex items-center gap-2">
          <button
            onClick={handleApprove}
            disabled={status === 'submitting'}
            className="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-medium rounded-lg shadow-sm transition-all text-xs"
          >
            {status === 'submitting' ? 'Submitting...' : 'Approve & Submit'}
          </button>
          <button
            onClick={() => setStatus('dismissed')}
            disabled={status === 'submitting'}
            className="px-3 py-1.5 text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200 text-xs transition-colors"
          >
            Dismiss
          </button>
        </div>
      )}
    </motion.div>
  );
}

function ExecutionTraceDrawer({ trace }: { trace: ExecutionTrace }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-2 text-xs">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 text-[11px] font-mono text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 bg-zinc-100 dark:bg-zinc-800/80 px-2.5 py-1 rounded-md border border-zinc-200/60 dark:border-zinc-700/50 transition-colors"
      >
        <span>⚡ Trace: {Math.round(trace.total_latency_ms)}ms · {trace.total_tokens} tokens (${trace.total_cost_usd.toFixed(5)})</span>
        <span className="text-[10px]">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-2 p-2.5 rounded-lg border border-zinc-200 dark:border-zinc-700/60 bg-zinc-50 dark:bg-zinc-900/60 font-mono text-[11px] space-y-1.5 text-left"
        >
          <div className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500 border-b border-zinc-200 dark:border-zinc-800 pb-1 flex justify-between">
            <span>Node Execution Waterfall</span>
            <span>Tokens / Cost</span>
          </div>
          {trace.nodes.map((n, i) => (
            <div key={i} className="flex justify-between items-center py-0.5">
              <span className="text-zinc-700 dark:text-zinc-300 font-medium">
                {n.node} <span className="text-zinc-400 text-[10px]">({n.latency_ms}ms)</span>
              </span>
              <span className="text-zinc-500 dark:text-zinc-400 text-[10px]">
                {n.total_tokens} tok · ${n.cost_usd.toFixed(5)}
              </span>
            </div>
          ))}
        </motion.div>
      )}
    </div>
  );
}

// ─── Chat Message Bubble ───────────────────────────────────────────────────────

function ChatMessageBubble({
  msg,
  isStreaming,
  employeeId,
  onConfirmed,
}: {
  msg: ChatMessage;
  isStreaming: boolean;
  employeeId?: string;
  onConfirmed?: () => void;
}) {
  const isUser = msg.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? 'bg-violet-600 text-white rounded-br-sm'
          : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 rounded-bl-sm'
      }`}>
        {isUser ? (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        ) : (
          <StreamingText text={msg.content} active={isStreaming} />
        )}
        {msg.toolCalls && msg.toolCalls.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {msg.toolCalls.map((t) => <ToolCallBadge key={t} name={t} />)}
          </div>
        )}
        {msg.citations && msg.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {msg.citations.map((c) => <CitationChip key={c} text={c} />)}
          </div>
        )}
        {msg.proposals && msg.proposals.length > 0 && (
          <div className="space-y-2">
            {msg.proposals.map((p) => (
              <ActionProposalCard
                key={p.action_id}
                proposal={p}
                employeeId={employeeId}
                onConfirmed={onConfirmed}
              />
            ))}
          </div>
        )}
        {msg.trace && (
          <ExecutionTraceDrawer trace={msg.trace} />
        )}
      </div>
    </motion.div>
  );
}

// ─── Circular Progress ─────────────────────────────────────────────────────────

function CircularProgress({ percent }: { percent: number }) {
  const r = 24;
  const circ = 2 * Math.PI * r;
  const offset = circ - (percent / 100) * circ;

  return (
    <div className="relative w-14 h-14 shrink-0">
      <svg width="56" height="56" viewBox="0 0 56 56" className="-rotate-90">
        <circle cx="28" cy="28" r={r} fill="none" strokeWidth="4.5"
          className="stroke-zinc-200 dark:stroke-zinc-800" />
        <motion.circle
          cx="28" cy="28" r={r} fill="none" strokeWidth="4.5"
          strokeLinecap="round"
          className="stroke-violet-500 dark:stroke-violet-400"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xs font-bold text-zinc-800 dark:text-zinc-200">{percent}%</span>
      </div>
    </div>
  );
}

// ─── Sidebar Tabs ─────────────────────────────────────────────────────────────

type SidebarTab = 'tasks' | 'docs' | 'payroll' | 'it' | 'persona';

const CATEGORY_STYLES: Record<string, string> = {
  HR:   'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400',
  IT:   'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400',
  Team: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400',
};

// Tab 1: Tasks Checklist
function TasksTabContent({
  status,
  onComplete,
  onReset,
}: {
  status: OnboardingStatus | null;
  onComplete: (id: number) => void;
  onReset: () => void;
}) {
  return (
    <div className="space-y-4">
      {status && (
        <div className="flex items-center gap-3 p-3 rounded-xl bg-zinc-100/70 dark:bg-zinc-800/60 border border-zinc-200/60 dark:border-zinc-700/40">
          <CircularProgress percent={status.completion_percent} />
          <div>
            <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
              {status.completed_tasks} of {status.total_tasks} completed
            </p>
            <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
              {status.completion_percent === 100 ? '🎉 Onboarding fully complete!' : 'Keep progressing on your Day 1 goals'}
            </p>
          </div>
        </div>
      )}

      <div className="space-y-1.5 max-h-[calc(100vh-320px)] overflow-y-auto pr-1">
        {(!status || status.tasks.length === 0) && (
          <p className="text-xs text-zinc-400 dark:text-zinc-600 italic py-4 text-center">
            No tasks yet. Ask the assistant what to do this week!
          </p>
        )}
        <AnimatePresence>
          {status?.tasks.map((task) => (
            <motion.button
              key={task.id}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              onClick={() => onComplete(task.id)}
              className="w-full flex items-start gap-2.5 p-2.5 rounded-lg text-left
                border border-transparent hover:border-zinc-200 dark:hover:border-zinc-800
                hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-all group"
            >
              <div className={`shrink-0 mt-0.5 w-4 h-4 rounded-full border flex items-center justify-center transition-colors
                ${task.status === 'completed'
                  ? 'bg-emerald-500 border-emerald-500 text-white'
                  : 'border-zinc-300 dark:border-zinc-700 group-hover:border-violet-400 dark:group-hover:border-violet-600'
                }`}
              >
                {task.status === 'completed' && <CheckIcon size={9} />}
              </div>
              <div className="flex-1 min-w-0">
                <p className={`text-xs leading-relaxed ${
                  task.status === 'completed'
                    ? 'line-through text-zinc-400 dark:text-zinc-600'
                    : 'text-zinc-700 dark:text-zinc-300 font-medium'
                }`}>
                  {task.title}
                </p>
                <div className="mt-1 flex items-center gap-1.5">
                  <span className={`rounded px-1.5 py-px text-[10px] font-medium ${
                    CATEGORY_STYLES[task.category] ?? 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
                  }`}>
                    {task.category}
                  </span>
                  <span className="text-[10px] text-zinc-400 dark:text-zinc-500">
                    Day {task.due_day}
                  </span>
                </div>
              </div>
            </motion.button>
          ))}
        </AnimatePresence>
      </div>

      <div className="pt-2 border-t border-zinc-200 dark:border-zinc-800 flex justify-end">
        <button
          onClick={onReset}
          className="text-[11px] text-zinc-400 dark:text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors"
        >
          Reset Onboarding Tasks
        </button>
      </div>
    </div>
  );
}

// Tab 2: Regulatory Document Vault
function DocumentsTabContent({
  employeeId,
  documents,
  onRefresh,
}: {
  employeeId: string;
  documents: EmployeeDocument[];
  onRefresh: () => void;
}) {
  const [signingCode, setSigningCode] = useState<string | null>(null);

  const handleSign = async (code: string) => {
    try {
      setSigningCode(code);
      await signEmployeeDocument(employeeId, code);
      onRefresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Signature failed');
    } finally {
      setSigningCode(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="p-2.5 rounded-lg bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200/60 dark:border-blue-900/40 text-[11px] text-blue-800 dark:text-blue-300">
        Regulatory documents are automatically tailored to your registered tax & legal residency.
      </div>

      <div className="space-y-2 max-h-[calc(100vh-320px)] overflow-y-auto pr-1">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="p-3 rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 shadow-xs space-y-2"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                  {doc.document_title}
                </p>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-500">
                    Due Day {doc.deadline_day}
                  </span>
                  {doc.mandatory && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 font-medium">
                      Mandatory
                    </span>
                  )}
                </div>
              </div>
              <div>
                {doc.status === 'signed' ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 text-[10px] font-semibold">
                    <CheckIcon size={10} /> Signed
                  </span>
                ) : (
                  <button
                    onClick={() => handleSign(doc.document_code)}
                    disabled={signingCode === doc.document_code}
                    className="px-2.5 py-1 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-md text-[11px] font-medium transition-colors"
                  >
                    {signingCode === doc.document_code ? 'Signing...' : 'Sign Now'}
                  </button>
                )}
              </div>
            </div>

            {doc.signed_at && (
              <p className="text-[10px] font-mono text-zinc-400 dark:text-zinc-500">
                Timestamp: {new Date(doc.signed_at).toLocaleString()}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// Tab 3: Payroll & Direct Deposit
function PayrollTabContent({
  employeeId,
  payroll,
  onRefresh,
}: {
  employeeId: string;
  payroll: PayrollProfile | null;
  onRefresh: () => void;
}) {
  const [bankName, setBankName] = useState('');
  const [accountLast4, setAccountLast4] = useState('');
  const [routingOrIfsc, setRoutingOrIfsc] = useState('');
  const [taxStatus, setTaxStatus] = useState('W4_SINGLE');
  const [currency, setCurrency] = useState('USD');
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const indianBankPrefixes: Record<string, string> = {
    SBI: 'SBIN',
    'State Bank of India': 'SBIN',
    HDFC: 'HDFC',
    'HDFC Bank': 'HDFC',
    ICICI: 'ICIC',
    'ICICI Bank': 'ICIC',
    'Axis Bank': 'UTIB',
    Kotak: 'KKBK',
    PNB: 'PUNB',
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (currency === 'USD' && !/^\d{9}$/.test(routingOrIfsc.trim())) {
      setFeedback('For USD, enter the 9-digit US ABA routing number.');
      return;
    }
    if (currency === 'INR' && !/^[A-Za-z]{4}0[A-Za-z0-9]{6}$/.test(routingOrIfsc.trim())) {
      const expectedPrefix = indianBankPrefixes[bankName.trim()];
      setFeedback(
        expectedPrefix
          ? `For ${bankName}, enter an 11-character IFSC beginning with ${expectedPrefix}0 (for example ${expectedPrefix}0001234).`
          : 'For INR, enter an 11-character IFSC code such as HDFC0001234.',
      );
      return;
    }
    if (currency === 'INR') {
      const expectedPrefix = indianBankPrefixes[bankName.trim()];
      if (expectedPrefix && !routingOrIfsc.trim().toUpperCase().startsWith(`${expectedPrefix}0`)) {
        setFeedback(`The IFSC code does not match ${bankName}. Use a code beginning with ${expectedPrefix}0.`);
        return;
      }
    }
    setSubmitting(true);
    setFeedback(null);
    try {
      const res = await submitPayroll(employeeId, bankName, accountLast4, routingOrIfsc, taxStatus, currency);
      setFeedback(res.message || 'Payroll details submitted successfully.');
      onRefresh();
      setBankName('');
      setAccountLast4('');
      setRoutingOrIfsc('');
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Current status card */}
      <div className="p-3 rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
            Disbursement Status
          </span>
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
            payroll?.status === 'submitted' || payroll?.status === 'verified'
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
              : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
          }`}>
            {payroll?.status?.replace(/_/g, ' ') || 'Pending Submission'}
          </span>
        </div>

        {payroll?.bank_name ? (
          <div className="font-mono text-xs space-y-1 text-zinc-600 dark:text-zinc-400 pt-1">
            <div className="flex justify-between">
              <span>Bank:</span>
              <span className="text-zinc-800 dark:text-zinc-200 font-medium">{payroll.bank_name}</span>
            </div>
            <div className="flex justify-between">
              <span>Account:</span>
              <span className="text-zinc-800 dark:text-zinc-200 font-medium">{payroll.account_number_masked}</span>
            </div>
            <div className="flex justify-between">
              <span>Routing/IFSC:</span>
              <span className="text-zinc-800 dark:text-zinc-200 font-medium">{payroll.routing_or_ifsc_code}</span>
            </div>
            <div className="flex justify-between">
              <span>Currency:</span>
              <span className="text-zinc-800 dark:text-zinc-200 font-medium">{payroll.currency}</span>
            </div>
          </div>
        ) : (
          <p className="text-[11px] text-zinc-400 dark:text-zinc-500 pt-1">
            No bank account linked. Submit your details below to ensure timely first salary disbursement.
          </p>
        )}
      </div>

      {/* Direct deposit form */}
      <form onSubmit={handleSubmit} className="p-3 rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 space-y-2.5 text-xs">
        <div className="flex items-center gap-1.5 text-violet-700 dark:text-violet-400 font-semibold">
          <ShieldCheckIcon size={14} />
          <span>Update Direct Deposit (PII Safe)</span>
        </div>

        <div>
          <label className="block text-[10px] text-zinc-400 dark:text-zinc-500 mb-1">Bank Name</label>
          <input
            type="text"
            required
            placeholder="e.g. JPMorgan Chase / Nordea"
            value={bankName}
            onChange={(e) => setBankName(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-xs text-zinc-800 dark:text-zinc-200"
          />
          {currency === 'INR' && (
            <p className="mt-1 text-[10px] text-zinc-400">
              Known bank prefixes are checked automatically (SBI: SBIN0, HDFC: HDFC0, ICICI: ICIC0).
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] text-zinc-400 dark:text-zinc-500 mb-1">
              Account Last 4 Digits
            </label>
            <input
              type="text"
              required
              maxLength={4}
              pattern="\d{4}"
              placeholder="4892"
              value={accountLast4}
              onChange={(e) => setAccountLast4(e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-xs text-zinc-800 dark:text-zinc-200 font-mono"
            />
          </div>
          <div>
            <label className="block text-[10px] text-zinc-400 dark:text-zinc-500 mb-1">
              Routing / IFSC
            </label>
            <input
              type="text"
              required
              placeholder="021000021"
              value={routingOrIfsc}
              onChange={(e) => setRoutingOrIfsc(e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-xs text-zinc-800 dark:text-zinc-200 font-mono"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] text-zinc-400 dark:text-zinc-500 mb-1">Currency</label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full px-2 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-xs text-zinc-800 dark:text-zinc-200"
            >
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
              <option value="INR">INR (₹)</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] text-zinc-400 dark:text-zinc-500 mb-1">Tax Regime</label>
            <select
              value={taxStatus}
              onChange={(e) => setTaxStatus(e.target.value)}
              className="w-full px-2 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-xs text-zinc-800 dark:text-zinc-200"
            >
              <option value="W4_SINGLE">W-4 Single</option>
              <option value="W4_MARRIED">W-4 Married</option>
              <option value="INDIA_NEW_REGIME">India New Regime</option>
              <option value="EU_STANDARD">EU Standard</option>
            </select>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-medium rounded-lg text-xs transition-colors"
        >
          {submitting ? 'Submitting...' : 'Save & Submit Details'}
        </button>

        {feedback && (
          <p className="text-[11px] text-zinc-600 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-800 p-2 rounded-lg">
            {feedback}
          </p>
        )}
      </form>
    </div>
  );
}

// Tab 4: IT & Security
function ITTabContent({
  employeeId,
  equipment,
  trainings,
  onRefresh,
}: {
  employeeId: string;
  equipment: EquipmentItem[];
  trainings: TrainingAssignment[];
  onRefresh: () => void;
}) {
  const [completingId, setCompletingId] = useState<number | null>(null);

  const handleCompleteTraining = async (id: number) => {
    try {
      setCompletingId(id);
      await completeTraining(employeeId, id);
      onRefresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to complete training');
    } finally {
      setCompletingId(null);
    }
  };

  const securityTraining = trainings.find((t) => t.training_name.toLowerCase().includes('security'));
  const isSecurityComplete = securityTraining?.status === 'completed';

  return (
    <div className="space-y-4">
      {/* Deterministic Compliance Gate status */}
      <div className={`p-3 rounded-xl border text-xs space-y-1.5 ${
        isSecurityComplete
          ? 'bg-emerald-50/70 border-emerald-200 dark:bg-emerald-950/30 dark:border-emerald-900/40 text-emerald-900 dark:text-emerald-300'
          : 'bg-amber-50/70 border-amber-200 dark:bg-amber-950/30 dark:border-amber-900/40 text-amber-900 dark:text-amber-300'
      }`}>
        <div className="flex items-center gap-1.5 font-semibold">
          <ShieldCheckIcon size={14} />
          <span>System Access Compliance Gate</span>
        </div>
        <p className="text-[11px]">
          {isSecurityComplete
            ? '✅ Security Awareness Training Completed: Production AWS, GitHub, and Cloud consoles are unlocked.'
            : '🔒 Access to GitHub & Production AWS is gated by policy until Security Awareness Training is completed.'}
        </p>
      </div>

      {/* Equipment Allocations */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
          Hardware & Peripherals
        </h3>
        <div className="space-y-1.5">
          {equipment.length === 0 && (
            <p className="text-[11px] text-zinc-400 italic">No equipment requested yet. Ask the AI in chat!</p>
          )}
          {equipment.map((item) => (
            <div
              key={item.id}
              className="p-2.5 rounded-lg border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 flex items-center justify-between text-xs"
            >
              <div>
                <p className="font-medium text-zinc-800 dark:text-zinc-200">{item.item_name}</p>
                <span className="text-[10px] text-zinc-400 capitalize">{item.item_type}</span>
              </div>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium capitalize ${
                item.status === 'delivered'
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                  : 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
              }`}>
                {item.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Compliance Trainings */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
          Mandatory Training Modules
        </h3>
        <div className="space-y-1.5">
          {trainings.map((t) => (
            <div
              key={t.id}
              className="p-2.5 rounded-lg border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 flex items-center justify-between text-xs"
            >
              <div>
                <p className="font-medium text-zinc-800 dark:text-zinc-200">{t.training_name}</p>
                <span className="text-[10px] text-zinc-400">Due Day {t.due_day}</span>
              </div>
              {t.status === 'completed' ? (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                  <CheckIcon size={12} /> Complete
                </span>
              ) : (
                <button
                  onClick={() => handleCompleteTraining(t.id)}
                  disabled={completingId === t.id}
                  className="px-2.5 py-1 bg-violet-600 hover:bg-violet-700 text-white rounded text-[11px] font-medium transition-colors"
                >
                  {completingId === t.id ? 'Saving...' : 'Mark Done'}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Tab 5: Persona & Region Switcher
function PersonaTabContent({
  employeeId,
  assignment,
  onRefresh,
}: {
  employeeId: string;
  assignment: EmployeeAssignment | null;
  onRefresh: () => void;
}) {
  const [location, setLocation] = useState(assignment?.location || 'Finland');
  const [workerType, setWorkerType] = useState(assignment?.worker_type || 'fte');
  const [department, setDepartment] = useState(assignment?.department || 'engineering');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (assignment) {
      if (assignment.location) setLocation(assignment.location);
      if (assignment.worker_type) setWorkerType(assignment.worker_type);
      if (assignment.department) setDepartment(assignment.department);
    }
  }, [assignment]);

  const handleUpdate = async () => {
    setSaving(true);
    try {
      await updatePersona(employeeId, {
        location,
        worker_type: workerType,
        department,
      });
      onRefresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3.5 text-xs">
      <div className="p-2.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-[11px] text-zinc-600 dark:text-zinc-400">
        Switch the employee’s profile to immediately test how RAG policies, holiday calendars, benefits, and legal documents dynamically adapt.
      </div>

      <div className="space-y-2.5">
        <div>
          <label className="block text-[11px] font-medium text-zinc-700 dark:text-zinc-300 mb-1">
            Country & Location
          </label>
          <select
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs"
          >
            <option value="Finland">Finland (Helsinki HQ) 🇫🇮</option>
            <option value="USA">United States (San Francisco) 🇺🇸</option>
            <option value="India">India (Bengaluru) 🇮🇳</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-medium text-zinc-700 dark:text-zinc-300 mb-1">
            Worker Classification
          </label>
          <select
            value={workerType}
            onChange={(e) => setWorkerType(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs"
          >
            <option value="fte">Full-Time Employee (W-2 / Contract) — Full Benefits</option>
            <option value="contractor">Contractor (1099/B2B) — Invoicing only, no 401(k)</option>
            <option value="intern">Intern — Limited PTO, standard laptop</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-medium text-zinc-700 dark:text-zinc-300 mb-1">
            Department
          </label>
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs"
          >
            <option value="engineering">Engineering (MacBook Pro M3, GitHub, AWS)</option>
            <option value="sales">Sales (ThinkPad T14s, Salesforce)</option>
            <option value="hr">Human Resources</option>
          </select>
        </div>

        <button
          onClick={handleUpdate}
          disabled={saving}
          className="w-full py-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-medium rounded-lg text-xs transition-colors"
        >
          {saving ? 'Applying...' : 'Apply Persona Switch'}
        </button>
      </div>

      {assignment && (
        <div className="pt-2 border-t border-zinc-200 dark:border-zinc-800 font-mono text-[11px] text-zinc-500 space-y-1">
          <div>Manager: {assignment.manager_name}</div>
          <div>Buddy: {assignment.buddy_name}</div>
        </div>
      )}
    </div>
  );
}

// ─── Demo Action Prompts ───────────────────────────────────────────────────────

interface DemoPrompt {
  label: string;
  badge: string;
  prompt: string;
}

const DEMO_PROMPTS: DemoPrompt[] = [
  {
    label: 'US I-9 & 401(k)',
    badge: 'USA 🇺🇸',
    prompt: 'What is the legal deadline for Form I-9 verification and how does 401(k) matching work in the USA?',
  },
  {
    label: 'India PF & Holidays',
    badge: 'India 🇮🇳',
    prompt: 'What statutory benefits like Provident Fund or Gratuity and public holidays are available in India?',
  },
  {
    label: 'Hardware Request',
    badge: 'HITL 🖥️',
    prompt: 'Please request a MacBook Pro 14-inch M3 and Dell UltraSharp 27 4K monitor for me.',
  },
  {
    label: 'Manager Check-in',
    badge: 'HITL 📅',
    prompt: 'Please schedule a check-in with my manager on day 7 to review my first week goals.',
  },
  {
    label: 'Contractor Benefits',
    badge: 'FSM ⚖️',
    prompt: 'Are contractors eligible for the company 401(k) matching program and dental insurance?',
  },
  {
    label: 'Cloud Credentials',
    badge: 'Gate 🛡️',
    prompt: 'Can I request production AWS credentials and GitHub write access today?',
  },
  {
    label: 'Direct Deposit',
    badge: 'Payroll 💳',
    prompt: 'How do I set up my direct deposit and bank details for salary disbursement?',
  },
];

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const { theme, toggle } = useTheme();
  const [employee, setEmployee] = useState<DemoEmployee | null>(null);
  const [employees, setEmployees] = useState<DemoEmployee[]>([]);
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [documents, setDocuments] = useState<EmployeeDocument[]>([]);
  const [payroll, setPayroll] = useState<PayrollProfile | null>(null);
  const [equipment, setEquipment] = useState<EquipmentItem[]>([]);
  const [trainings, setTrainings] = useState<TrainingAssignment[]>([]);
  const [assignment, setAssignment] = useState<EmployeeAssignment | null>(null);

  const [activeTab, setActiveTab] = useState<SidebarTab>('tasks');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentLog, setAgentLog] = useState<AgentEvent[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const refreshAll = useCallback(async (employeeId: string) => {
    try {
      const [s, docs, pay, eq, tr, asgn] = await Promise.all([
        fetchOnboardingStatus(employeeId),
        fetchDocuments(employeeId),
        fetchPayroll(employeeId),
        fetchEquipment(employeeId),
        fetchTrainings(employeeId),
        fetchAssignments(employeeId),
      ]);
      setStatus(s);
      setDocuments(docs);
      setPayroll(pay);
      setEquipment(eq);
      setTrainings(tr);
      setAssignment(asgn);
    } catch (err) {
      console.error('Error refreshing data:', err);
    }
  }, []);

  const selectEmployee = useCallback((emp: DemoEmployee) => {
      if (emp.access_token) setAuthToken(emp.access_token);
      setEmployee(emp);
      setMessages([]);
      setError(null);
      refreshAll(emp.id);
  }, [refreshAll]);

  useEffect(() => {
    fetchDemoEmployees().then((list) => {
      setEmployees(list);
      const current = list[0];
      if (current) selectEmployee(current);
    }).catch(console.error);
  }, [selectEmployee]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || !employee || loading) return;

    setInput('');
    setError(null);
    setLoading(true);
    setAgentLog([]);
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.focus();
    }

    const userMsg: ChatMessage = { role: 'user', content: message };
    setMessages((prev) => [...prev, userMsg]);

    let assistantContent = '';
    let citations: string[] = [];
    let toolCalls: string[] = [];
    let agentEvents: AgentEvent[] = [];
    let proposals: ActionProposal[] = [];
    let trace: ExecutionTrace | undefined = undefined;

    try {
      await streamChat(message, employee.id, messages, (event, data) => {
        if (event === 'token') {
          assistantContent += data as string;
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === 'assistant') {
              next[next.length - 1] = {
                ...last,
                content: assistantContent,
                citations,
                toolCalls,
                agentEvents,
                proposals: proposals.length > 0 ? proposals : undefined,
                trace,
              };
            } else {
              next.push({
                role: 'assistant',
                content: assistantContent,
                citations,
                toolCalls,
                agentEvents,
                proposals: proposals.length > 0 ? proposals : undefined,
                trace,
              });
            }
            return next;
          });
        }
        if (event === 'citations') citations = data as string[];
        if (event === 'tool_calls') {
          toolCalls = (data as { name: string }[]).map((t) => t.name);
        }
        if (event === 'action_proposal') {
          const prop = data as ActionProposal;
          if (!proposals.some((p) => p.action_id === prop.action_id)) {
            proposals = [...proposals, prop];
          }
        }
        if (event === 'telemetry') {
          trace = data as ExecutionTrace;
        }
        if (event === 'agent_log') {
          const entry = data as AgentEvent;
          setAgentLog((prev) => [...prev, entry]);
          agentEvents = [...agentEvents, entry];
        }
        if (event === 'agent_events') {
          agentEvents = data as AgentEvent[];
        }
        if (event === 'done') {
          assistantContent = data as string;
        }
        if (event === 'error') {
          throw new Error((data as { message: string }).message);
        }
      });

      setMessages((prev) => {
        const next = [...prev];
        const idx = next.findIndex((m, i) => m.role === 'assistant' && i === next.length - 1);
        const assistantMsg: ChatMessage = {
          role: 'assistant',
          content: assistantContent,
          citations,
          toolCalls,
          agentEvents,
          proposals: proposals.length > 0 ? proposals : undefined,
          trace,
        };
        if (idx >= 0) next[idx] = assistantMsg;
        else next.push(assistantMsg);
        return next;
      });

      await refreshAll(employee.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = async (taskId: number) => {
    if (!employee) return;
    await completeTask(employee.id, taskId);
    await refreshAll(employee.id);
  };

  const handleReset = async () => {
    if (!employee) return;
    await resetOnboarding(employee.id);
    setMessages([]);
    setAgentLog([]);
    await refreshAll(employee.id);
  };

  const showThinking =
    loading &&
    (messages.length === 0 ||
      messages[messages.length - 1]?.role === 'user' ||
      (messages[messages.length - 1]?.role === 'assistant' &&
        !messages[messages.length - 1]?.content));

  return (
    <div className="h-screen flex flex-col bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 overflow-hidden">
      {/* ── Top Navigation Bar ── */}
      <header className="h-14 shrink-0 px-4 flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-violet-600 flex items-center justify-center text-white font-bold text-sm shadow-sm">
            OA
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">OnboardAI</h1>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300 font-semibold tracking-wide">
                ENTERPRISE
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 dark:text-zinc-500">
              Autonomous Multi-Agent HR Assistant
            </p>
          </div>
        </div>

        {/* Current Active Persona summary */}
        {employee && (
          <div className="hidden md:flex items-center gap-2 text-xs text-zinc-500 bg-zinc-100/80 dark:bg-zinc-800/80 px-3 py-1.5 rounded-full border border-zinc-200/60 dark:border-zinc-700/50">
            {employees.length > 1 && (
              <select
                value={employee.id}
                onChange={(event) => {
                  const selected = employees.find((item) => item.id === event.target.value);
                  if (selected) selectEmployee(selected);
                }}
                className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900"
                aria-label="Select demo employee"
              >
                {employees.map((item) => (
                  <option key={item.id} value={item.id}>{item.name} · {item.location}</option>
                ))}
              </select>
            )}
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="font-medium text-zinc-800 dark:text-zinc-200">{employee.name}</span>
            <span>·</span>
            <span>{assignment?.location || 'Finland'}</span>
            <span>·</span>
            <span className="uppercase text-[10px] font-semibold text-violet-600 dark:text-violet-400">
              {assignment?.worker_type || 'FTE'}
            </span>
          </div>
        )}

        <div className="flex items-center gap-2">
          <Link
            to="/admin/checkins"
            className="text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 px-2 py-1 rounded transition-colors"
          >
            Check-ins Admin
          </Link>
          <Link
            to="/admin/evals"
            className="text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 px-2 py-1 rounded transition-colors"
          >
            Evals Suite (36)
          </Link>
          <Link
            to={employee ? `/dashboard?employeeId=${encodeURIComponent(employee.id)}` : '/dashboard'}
            className="text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 px-2 py-1 rounded transition-colors"
          >
            Control tower
          </Link>

          <button
            onClick={toggle}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>

      {/* ── Main Work Area ── */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Left Column: Chat conversation */}
        <main className="flex-1 flex flex-col min-w-0 border-r border-zinc-200 dark:border-zinc-800">
          {/* Messages list */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3.5">
            <AnimatePresence initial={false}>
              {messages.length === 0 && !loading && (
                <div className="flex flex-col items-center justify-center h-full gap-5 pb-8 max-w-lg mx-auto text-center">
                  <div className="w-12 h-12 rounded-2xl bg-violet-100 dark:bg-violet-900/40 flex items-center justify-center text-violet-600 dark:text-violet-300">
                    <ShieldCheckIcon size={24} />
                  </div>
                  <div>
                    <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                      Welcome to OnboardAI Enterprise
                    </h2>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 max-w-sm">
                      Autonomous HR agent with multi-region compliance, two-way HITL action confirmation, and deterministic policy gates.
                    </p>
                  </div>

                  <div className="w-full space-y-2 pt-2">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 text-left px-1">
                      One-Click Demo Capabilities:
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
                      {DEMO_PROMPTS.slice(0, 6).map((dp) => (
                        <button
                          key={dp.label}
                          onClick={() => handleSend(dp.prompt)}
                          className="p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/80 hover:border-violet-400 dark:hover:border-violet-600 hover:bg-violet-50/50 dark:hover:bg-violet-950/20 transition-all text-left shadow-2xs group"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-semibold text-zinc-800 dark:text-zinc-200 group-hover:text-violet-600">
                              {dp.label}
                            </span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-500">
                              {dp.badge}
                            </span>
                          </div>
                          <p className="text-[11px] text-zinc-400 dark:text-zinc-500 line-clamp-1">
                            {dp.prompt}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {messages.map((msg, i) => {
                if (msg.role === 'assistant' && !msg.content && loading) return null;
                const isStreaming = loading && i === messages.length - 1 && msg.role === 'assistant';
                return (
                  <ChatMessageBubble
                    key={i}
                    msg={msg}
                    isStreaming={isStreaming}
                    employeeId={employee?.id}
                    onConfirmed={() => employee && refreshAll(employee.id)}
                  />
                );
              })}

              {showThinking && (
                <motion.div key="thinking" className="flex justify-start">
                  <div className="rounded-2xl rounded-bl-sm bg-zinc-100 dark:bg-zinc-800">
                    <ThinkingDots />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div ref={chatEndRef} />
          </div>

          {/* Quick-Prompt Interactive Pills above Input */}
          <div className="px-4 py-2 border-t border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/30 flex items-center gap-1.5 overflow-x-auto no-scrollbar">
            <span className="text-[10px] font-semibold text-zinc-400 shrink-0 uppercase tracking-wider mr-1">
              Try:
            </span>
            {DEMO_PROMPTS.map((dp) => (
              <button
                key={dp.label}
                onClick={() => handleSend(dp.prompt)}
                className="shrink-0 text-[11px] px-2.5 py-1 rounded-full border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:border-violet-400 dark:hover:border-violet-600 hover:text-violet-600 dark:hover:text-violet-300 transition-colors"
              >
                {dp.badge} {dp.label}
              </button>
            ))}
          </div>

          {/* Multi-Agent flow timeline */}
          <AnimatePresence>
            {agentLog.length > 0 && (
              <AgentFlowPanel key="agentflow" entries={agentLog} />
            )}
          </AnimatePresence>

          {/* Error banner */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                className="mx-4 mb-2 p-2.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 text-xs text-rose-700 dark:text-rose-300"
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Input box */}
          <div className="p-3 border-t border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
            <div className="flex items-center gap-2 p-1.5 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-950 focus-within:border-violet-500 focus-within:ring-2 focus-within:ring-violet-500/20 transition-all">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                rows={1}
                placeholder="Ask about policies, benefits, request equipment, or schedule check-ins..."
                className="flex-1 bg-transparent border-0 resize-none px-2 py-1 text-xs text-zinc-800 dark:text-zinc-200 placeholder-zinc-400 focus:outline-hidden max-h-32"
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || loading}
                className="w-8 h-8 rounded-lg bg-violet-600 hover:bg-violet-700 disabled:opacity-40 text-white flex items-center justify-center shrink-0 transition-all shadow-xs"
              >
                <SendIcon />
              </button>
            </div>
          </div>
        </main>

        {/* Right Column: Tabbed Onboarding Hub Sidebar */}
        <aside className="w-80 md:w-96 shrink-0 flex flex-col bg-white dark:bg-zinc-900/60 h-full overflow-hidden">
          {/* Tabs header */}
          <div className="p-2 border-b border-zinc-200 dark:border-zinc-800 flex items-center gap-1 overflow-x-auto no-scrollbar">
            <button
              onClick={() => setActiveTab('tasks')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'tasks'
                  ? 'bg-violet-600 text-white shadow-xs'
                  : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800'
              }`}
            >
              📋 Checklist
            </button>
            <button
              onClick={() => setActiveTab('docs')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'docs'
                  ? 'bg-violet-600 text-white shadow-xs'
                  : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800'
              }`}
            >
              📄 Vault
            </button>
            <button
              onClick={() => setActiveTab('payroll')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'payroll'
                  ? 'bg-violet-600 text-white shadow-xs'
                  : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800'
              }`}
            >
              💳 Payroll
            </button>
            <button
              onClick={() => setActiveTab('it')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'it'
                  ? 'bg-violet-600 text-white shadow-xs'
                  : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800'
              }`}
            >
              💻 IT / Security
            </button>
            <button
              onClick={() => setActiveTab('persona')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'persona'
                  ? 'bg-violet-600 text-white shadow-xs'
                  : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800'
              }`}
            >
              👤 Persona
            </button>
          </div>

          {/* Tab Content Body */}
          <div className="flex-1 overflow-y-auto p-4">
            {employee && (
              <>
                {activeTab === 'tasks' && (
                  <TasksTabContent
                    status={status}
                    onComplete={handleComplete}
                    onReset={handleReset}
                  />
                )}
                {activeTab === 'docs' && (
                  <DocumentsTabContent
                    employeeId={employee.id}
                    documents={documents}
                    onRefresh={() => refreshAll(employee.id)}
                  />
                )}
                {activeTab === 'payroll' && (
                  <PayrollTabContent
                    employeeId={employee.id}
                    payroll={payroll}
                    onRefresh={() => refreshAll(employee.id)}
                  />
                )}
                {activeTab === 'it' && (
                  <ITTabContent
                    employeeId={employee.id}
                    equipment={equipment}
                    trainings={trainings}
                    onRefresh={() => refreshAll(employee.id)}
                  />
                )}
                {activeTab === 'persona' && (
                  <PersonaTabContent
                    employeeId={employee.id}
                    assignment={assignment}
                    onRefresh={() => refreshAll(employee.id)}
                  />
                )}
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
