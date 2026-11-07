const API_BASE = import.meta.env.VITE_API_URL || '';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
  toolCalls?: string[];
  agentEvents?: AgentEvent[];
  proposals?: ActionProposal[];
  trace?: ExecutionTrace;
}

export interface AgentEvent {
  agent: string;
  status: string;
  detail: string;
}

export interface OnboardingTask {
  id: number;
  title: string;
  due_day: number;
  category: string;
  status: string;
  required?: boolean;
  owner?: string;
  blocked_reason?: string | null;
  dependencies?: number[];
}

export interface OnboardingStatus {
  employee_id: string;
  total_tasks: number;
  completed_tasks: number;
  completion_percent: number;
  tasks: OnboardingTask[];
}

export interface EmployeeProfile {
  employee_id: string;
  name: string;
  role: string;
  department: string;
  start_date: string;
  employment_type: string;
  work_mode: string;
  location: string;
}

export interface Readiness {
  employee_id: string;
  readiness_percent: number;
  mandatory_blockers: number;
  components: Record<string, number>;
  exceptions: Record<string, unknown>[];
}

export interface Approval {
  id: number;
  employee_id: string;
  action: string;
  resource_type: string;
  status: string;
  requested_by: string;
  approved_by?: string;
  reason?: string;
  created_at: string;
}

export interface Execution {
  id: number;
  execution_id: string;
  employee_id: string;
  message_hash: string;
  status: string;
  tool_calls: unknown[];
  error?: string;
  started_at: string;
  completed_at?: string;
}

function adminHeaders(adminKey?: string): Record<string, string> {
  const key = adminKey || import.meta.env.VITE_ADMIN_API_KEY;
  return authHeaders(key ? { 'X-Admin-Key': key } : {});
}

export interface DemoEmployee {
  id: string;
  name: string;
  role: string;
  start_day: number;
  company: string;
  location?: string;
  manager?: string;
  buddy?: string;
  access_token?: string;
  department?: string;
  employment_type?: string;
  work_mode?: string;
}

export interface EquipmentItem {
  id: number;
  employee_id: string;
  item_type: string;
  item_name: string;
  status: string;
  allocated_at?: string;
  created_at: string;
}

export interface TrainingAssignment {
  id: number;
  employee_id: string;
  training_name: string;
  due_day: number;
  status: string;
  created_at: string;
}

export interface EmployeeAssignment {
  employee_id: string;
  manager_name?: string;
  manager_email?: string;
  buddy_name?: string;
  buddy_email?: string;
  location?: string;
  worker_type?: string;
  department?: string;
  onboarding_stage?: string;
}

// Phase 1: Payroll & Document interfaces
export interface PayrollProfile {
  employee_id: string;
  bank_name?: string;
  account_number_masked?: string;
  routing_or_ifsc_code?: string;
  currency: string;
  tax_filing_status?: string;
  withholding_allowances: number;
  status: string;
  verified_at?: string;
  message?: string;
}

export interface EmployeeDocument {
  id: number;
  employee_id: string;
  document_code: string;
  document_title: string;
  mandatory: boolean;
  deadline_day: number;
  status: string;
  signed_at?: string;
  verified_by?: string;
  created_at: string;
}

// Phase 3: HITL Action Proposal
export interface ActionProposal {
  status: 'proposed';
  action_type: string;
  action_id: string;
  title: string;
  details: Record<string, unknown>;
}

// Phase 4: Execution Trace
export interface ExecutionTrace {
  total_latency_ms: number;
  total_tokens: number;
  total_cost_usd: number;
  nodes: {
    node: string;
    latency_ms: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost_usd: number;
  }[];
}

export interface Checkin {
  id: number;
  employee_id: string;
  day: number;
  topic: string;
  scheduled_at: string;
}

export interface EvalScenarioResult {
  id: string;
  input: string;
  passed?: boolean;
  error?: string;
  checks?: Record<string, boolean>;
  metrics?: { name: string; score: number | null; passed: boolean; reason?: string }[];
  response_preview?: string;
  tool_calls?: string[];
}

export interface EvalReport {
  timestamp?: string;
  total: number;
  passed: number;
  failed: number;
  pass_rate_percent: number;
  framework?: string;
  results: EvalScenarioResult[];
}

export interface EvalSuiteReport {
  available: boolean;
  path: string;
  report: EvalReport | null;
}

export interface EvalReportBundle {
  results_dir: string;
  golden: EvalSuiteReport;
  deepeval: EvalSuiteReport;
}

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem('onboardai_token');
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem('onboardai_token', token);
    } else {
      localStorage.removeItem('onboardai_token');
    }
  } catch {
    // Ignore storage errors in restricted contexts
  }
}

function authHeaders(custom: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...custom };
  const token = getAuthToken();
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function loginUser(
  username: string,
  password: string,
): Promise<{ access_token: string; user_id: string; role: string }> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  setAuthToken(data.access_token);
  return data;
}

export async function fetchCurrentUser(): Promise<{ sub: string; role: string } | null> {
  const token = getAuthToken();
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/api/auth/me`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      setAuthToken(null);
      return null;
    }
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchEvalResults(): Promise<EvalReportBundle> {
  const res = await fetch(`${API_BASE}/api/evals/results`, { headers: authHeaders() });
  if (!res.ok) {
    const text = await res.text();
    if (res.status === 404) {
      throw new Error(
        'Eval API not found. Rebuild containers: docker-compose up -d --build backend frontend',
      );
    }
    throw new Error(`Failed to fetch eval results (${res.status}): ${text}`);
  }
  return res.json();
}

export async function fetchDemoEmployee(employeeId?: string): Promise<DemoEmployee> {
  const path = employeeId
    ? `/api/employee/demo/${encodeURIComponent(employeeId)}`
    : '/api/employee/demo';
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  const data: DemoEmployee = await res.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function fetchDemoEmployees(): Promise<DemoEmployee[]> {
  const res = await fetch(`${API_BASE}/api/employees/demo`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()).employees || [];
}

export async function fetchOnboardingStatus(employeeId: string): Promise<OnboardingStatus> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/status`, { headers: authHeaders() });
  return res.json();
}

export async function fetchEmployeeProfile(employeeId: string): Promise<EmployeeProfile> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/profile`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchReadiness(employeeId: string): Promise<Readiness> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/readiness`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchExceptions(employeeId: string): Promise<Record<string, unknown>[]> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/exceptions`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.exceptions || [];
}

export async function updateEmployeeProfile(
  employeeId: string,
  profile: Partial<EmployeeProfile>,
  adminKey?: string,
): Promise<EmployeeProfile> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...adminHeaders(adminKey) },
    body: JSON.stringify(profile),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchApprovals(employeeId?: string, adminKey?: string): Promise<Approval[]> {
  const query = employeeId ? `?employee_id=${encodeURIComponent(employeeId)}` : '';
  const res = await fetch(`${API_BASE}/api/admin/approvals${query}`, { headers: adminHeaders(adminKey) });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()).approvals || [];
}

export async function decideApproval(
  approvalId: number,
  status: 'approved' | 'rejected',
  approvedBy: string,
  adminKey?: string,
): Promise<Approval> {
  const res = await fetch(`${API_BASE}/api/admin/approvals/${approvalId}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...adminHeaders(adminKey) },
    body: JSON.stringify({ status, approved_by: approvedBy }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchExecutions(employeeId?: string, adminKey?: string): Promise<Execution[]> {
  const query = employeeId ? `?employee_id=${encodeURIComponent(employeeId)}` : '';
  const res = await fetch(`${API_BASE}/api/admin/executions${query}`, { headers: adminHeaders(adminKey) });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()).executions || [];
}

export async function completeTask(employeeId: string, taskId: number): Promise<void> {
  await fetch(`${API_BASE}/api/onboarding/${employeeId}/tasks/${taskId}/complete`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ employee_id: employeeId }),
  });
}

export async function resetOnboarding(employeeId: string, adminKey?: string): Promise<void> {
  const headers: Record<string, string> = {};
  if (adminKey) headers['X-Admin-Key'] = adminKey;
  await fetch(`${API_BASE}/api/onboarding/${employeeId}/reset`, { method: 'POST', headers: authHeaders(headers) });
}

export async function fetchEquipment(employeeId: string): Promise<EquipmentItem[]> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/equipment`, { headers: authHeaders() });
  if (!res.ok) return [];
  const data = await res.json();
  return data.equipment || [];
}

export async function requestEquipment(
  employeeId: string,
  itemType: string,
  itemName: string,
): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/equipment/request`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ item_type: itemType, item_name: itemName }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchTrainings(employeeId: string): Promise<TrainingAssignment[]> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/trainings`, { headers: authHeaders() });
  if (!res.ok) return [];
  const data = await res.json();
  return data.trainings || [];
}

export async function completeTraining(employeeId: string, trainingId: number): Promise<void> {
  await fetch(`${API_BASE}/api/onboarding/${employeeId}/trainings/${trainingId}/complete`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function fetchAssignments(employeeId: string): Promise<EmployeeAssignment> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/assignments`, { headers: authHeaders() });
  return res.json();
}

export async function updateAssignments(
  employeeId: string,
  data: Partial<EmployeeAssignment>,
  adminKey?: string,
): Promise<EmployeeAssignment> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (adminKey) headers['X-Admin-Key'] = adminKey;
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/assignments`, {
    method: 'POST',
    headers: authHeaders(headers),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updatePersona(
  employeeId: string,
  data: {
    location?: string;
    worker_type?: string;
    department?: string;
    onboarding_stage?: string;
  },
): Promise<EmployeeAssignment> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/persona`, {
    method: 'PATCH',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchCheckins(employeeId?: string, adminKey?: string): Promise<Checkin[]> {
  const params = employeeId ? `?employee_id=${encodeURIComponent(employeeId)}` : '';
  const headers: Record<string, string> = {};
  if (adminKey) headers['X-Admin-Key'] = adminKey;
  const res = await fetch(`${API_BASE}/api/admin/checkins${params}`, { headers: authHeaders(headers) });
  if (!res.ok) throw new Error('Failed to fetch check-ins');
  const data = await res.json();
  return data.checkins;
}

// Phase 1: Payroll API
export async function fetchPayroll(employeeId: string): Promise<PayrollProfile> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/payroll`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await formatApiError(res, 'Unable to load payroll details'));
  return res.json();
}

export async function submitPayroll(
  employeeId: string,
  bankName: string,
  accountLast4: string,
  routingOrIfsc: string,
  taxStatus: string,
  currency = 'EUR',
): Promise<PayrollProfile> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/payroll/submit`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      bank_name: bankName,
      account_number_last4: accountLast4,
      routing_or_ifsc_code: routingOrIfsc,
      tax_filing_status: taxStatus,
      currency,
    }),
  });
  if (!res.ok) throw new Error(await formatApiError(res, 'Unable to submit payroll details'));
  return res.json();
}

async function formatApiError(res: Response, fallback: string): Promise<string> {
  let detail = '';
  try {
    const data = await res.json();
    detail = typeof data.detail === 'string' ? data.detail : '';
  } catch {
    detail = '';
  }
  return detail ? `${fallback}: ${detail}` : `${fallback} (HTTP ${res.status})`;
}

// Phase 1: Documents API
export async function fetchDocuments(employeeId: string): Promise<EmployeeDocument[]> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/documents`, { headers: authHeaders() });
  if (!res.ok) return [];
  const data = await res.json();
  return data.documents || [];
}

export async function signEmployeeDocument(
  employeeId: string,
  documentCode: string,
): Promise<EmployeeDocument> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/documents/sign`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ document_code: documentCode }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Phase 3: HITL Action Execution
export async function executeConfirmedAction(
  employeeId: string,
  actionType: string,
  payload: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/actions/execute`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ action_type: actionType, payload }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function sendChat(
  message: string,
  employeeId: string,
  history: ChatMessage[],
): Promise<{ response: string; tool_calls: { name: string }[]; citations: string[] }> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      message,
      employee_id: employeeId,
      history: history.map((m) => ({ role: m.role, content: m.content })),
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function streamChat(
  message: string,
  employeeId: string,
  history: ChatMessage[],
  onEvent: (event: string, data: unknown) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      message,
      employee_id: employeeId,
      history: history.map((m) => ({ role: m.role, content: m.content })),
    }),
  });
  if (!res.ok || !res.body) throw new Error('Stream failed');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    for (const part of parts) {
      const lines = part.split('\n');
      let event = 'message';
      let data = '';
      for (const line of lines) {
        if (line.startsWith('event: ')) event = line.slice(7);
        if (line.startsWith('data: ')) data = line.slice(6);
      }
      if (data) onEvent(event, JSON.parse(data));
    }
  }
}
