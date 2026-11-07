import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  decideApproval,
  fetchDemoEmployee,
  fetchApprovals,
  fetchExceptions,
  fetchExecutions,
  fetchOnboardingStatus,
  fetchReadiness,
} from '../api';
import type { Approval, Execution, OnboardingStatus, Readiness } from '../api';

export default function OnboardingDashboard() {
  const [searchParams] = useSearchParams();
  const employeeId = searchParams.get('employeeId') || 'alex-chen';
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [employeeName, setEmployeeName] = useState('Alex Chen');
  const [exceptions, setExceptions] = useState<Record<string, unknown>[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [adminKey, setAdminKey] = useState(() => localStorage.getItem('onboardai_admin_key') || '');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [nextStatus, nextReadiness, nextExceptions] = await Promise.all([
        fetchOnboardingStatus(employeeId),
        fetchReadiness(employeeId),
        fetchExceptions(employeeId),
      ]);
      setStatus(nextStatus);
      setReadiness(nextReadiness);
      setExceptions(nextExceptions);
      if (adminKey) {
        const [nextApprovals, nextExecutions] = await Promise.all([
          fetchApprovals(undefined, adminKey),
          fetchExecutions(undefined, adminKey),
        ]);
        setApprovals(nextApprovals);
        setExecutions(nextExecutions);
      } else {
        setApprovals([]);
        setExecutions([]);
      }
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load onboarding dashboard');
    }
  }, [adminKey, employeeId]);

  useEffect(() => {
    void (async () => {
      try {
        const employee = await fetchDemoEmployee(employeeId);
        setEmployeeName(employee.name);
      } catch {
        setEmployeeName(employeeId);
      }
      await load();
    })();
  }, [employeeId, load]);

  const decide = async (id: number, decision: 'approved' | 'rejected') => {
    try {
      await decideApproval(id, decision, 'admin', adminKey);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to decide approval');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-indigo-600">Onboarding control tower</p>
            <h1 className="text-xl font-semibold">{employeeName} readiness dashboard</h1>
            <p className="text-sm text-slate-500">A single view of blockers, approvals, and agent reliability.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => void load()} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white">
              Refresh
            </button>
            <Link to="/" className="rounded-lg border border-slate-200 px-3 py-2 text-sm">Back to chat</Link>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl space-y-6 p-6">
        <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex-1">
            <label htmlFor="dashboard-admin-key" className="mb-1 block text-xs font-medium text-slate-500">
              Admin key for approvals and execution history
            </label>
            <input
              id="dashboard-admin-key"
              type="password"
              value={adminKey}
              onChange={(event) => {
                setAdminKey(event.target.value);
                localStorage.setItem('onboardai_admin_key', event.target.value);
              }}
              placeholder="Optional for employee readiness view"
              className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
            />
          </div>
          <span className="text-xs text-slate-500">Readiness remains available without admin access.</span>
        </div>
        {error && <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        <section className="grid gap-4 md:grid-cols-4">
          <Metric label="Readiness" value={`${readiness?.readiness_percent ?? 0}%`} />
          <Metric label="Tasks complete" value={`${status?.completed_tasks ?? 0}/${status?.total_tasks ?? 0}`} />
          <Metric label="Mandatory blockers" value={`${readiness?.mandatory_blockers ?? 0}`} alert={Boolean(readiness?.mandatory_blockers)} />
          <Metric label="Exceptions" value={`${exceptions.length}`} alert={exceptions.length > 0} />
        </section>
        <section className="grid gap-6 lg:grid-cols-2">
          <Panel title="Workflow and blockers">
            <div className="space-y-2">
              {(status?.tasks ?? []).map((task) => (
                <div key={task.id} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2">
                  <div>
                    <p className="text-sm font-medium">{task.title}</p>
                    <p className="text-xs text-slate-500">Day {task.due_day} · {task.owner || 'employee'}</p>
                  </div>
                  <span className={`rounded-full px-2 py-1 text-xs ${task.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : task.status === 'blocked' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>
                    {task.status}
                  </span>
                </div>
              ))}
              {!status?.tasks.length && <p className="text-sm text-slate-500">No tasks created yet.</p>}
            </div>
          </Panel>
          <Panel title="Approval queue">
            <div className="space-y-2">
              {approvals.filter((item) => item.status === 'pending').map((approval) => (
                <div key={approval.id} className="rounded-lg border border-slate-100 p-3">
                  <p className="text-sm font-medium">{approval.action}</p>
                  <p className="text-xs text-slate-500">{approval.employee_id} · {approval.resource_type} · {approval.reason || 'No reason provided'}</p>
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => void decide(approval.id, 'approved')} className="rounded bg-emerald-600 px-2 py-1 text-xs text-white">Approve</button>
                    <button onClick={() => void decide(approval.id, 'rejected')} className="rounded bg-red-600 px-2 py-1 text-xs text-white">Reject</button>
                  </div>
                </div>
              ))}
              {!approvals.some((item) => item.status === 'pending') && <p className="text-sm text-slate-500">No pending approvals.</p>}
            </div>
          </Panel>
        </section>
        <Panel title="Agent execution timeline">
          <div className="space-y-2">
            {executions.slice(0, 10).map((execution) => (
              <div key={execution.execution_id} className="flex items-center justify-between border-b border-slate-100 py-2 text-sm last:border-0">
                <span className="truncate pr-4 text-slate-600">{execution.message_hash.slice(0, 12)}…</span>
                <span className={execution.status === 'completed' ? 'text-emerald-700' : execution.status === 'failed' ? 'text-red-700' : 'text-amber-700'}>{execution.status}</span>
              </div>
            ))}
            {!executions.length && <p className="text-sm text-slate-500">No agent executions recorded yet.</p>}
          </div>
        </Panel>
      </main>
    </div>
  );
}

function Metric({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs uppercase tracking-wide text-slate-500">{label}</p><p className={`mt-2 text-2xl font-semibold ${alert ? 'text-red-600' : 'text-slate-900'}`}>{value}</p></div>;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="mb-4 font-semibold">{title}</h2>{children}</section>;
}
