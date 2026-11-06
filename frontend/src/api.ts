const API_BASE = import.meta.env.VITE_API_URL || '';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
  toolCalls?: string[];
  agentEvents?: AgentEvent[];
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
}

export interface OnboardingStatus {
  employee_id: string;
  total_tasks: number;
  completed_tasks: number;
  completion_percent: number;
  tasks: OnboardingTask[];
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

export async function fetchEvalResults(): Promise<EvalReportBundle> {
  const res = await fetch(`${API_BASE}/api/evals/results`);
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

export async function fetchDemoEmployee(): Promise<DemoEmployee> {
  const res = await fetch(`${API_BASE}/api/employee/demo`);
  return res.json();
}

export async function fetchOnboardingStatus(employeeId: string): Promise<OnboardingStatus> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/status`);
  return res.json();
}

export async function completeTask(employeeId: string, taskId: number): Promise<void> {
  await fetch(`${API_BASE}/api/onboarding/${employeeId}/tasks/${taskId}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ employee_id: employeeId }),
  });
}

export async function resetOnboarding(employeeId: string, adminKey?: string): Promise<void> {
  const headers: Record<string, string> = {};
  if (adminKey) headers['X-Admin-Key'] = adminKey;
  await fetch(`${API_BASE}/api/onboarding/${employeeId}/reset`, { method: 'POST', headers });
}

export async function fetchEquipment(employeeId: string): Promise<EquipmentItem[]> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/equipment`);
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item_type: itemType, item_name: itemName }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchTrainings(employeeId: string): Promise<TrainingAssignment[]> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/trainings`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.trainings || [];
}

export async function completeTraining(employeeId: string, trainingId: number): Promise<void> {
  await fetch(`${API_BASE}/api/onboarding/${employeeId}/trainings/${trainingId}/complete`, {
    method: 'POST',
  });
}

export async function fetchAssignments(employeeId: string): Promise<EmployeeAssignment> {
  const res = await fetch(`${API_BASE}/api/onboarding/${employeeId}/assignments`);
  return res.json();
}

export async function fetchCheckins(employeeId?: string, adminKey?: string): Promise<Checkin[]> {
  const params = employeeId ? `?employee_id=${encodeURIComponent(employeeId)}` : '';
  const headers: Record<string, string> = {};
  if (adminKey) headers['X-Admin-Key'] = adminKey;
  const res = await fetch(`${API_BASE}/api/admin/checkins${params}`, { headers });
  if (!res.ok) throw new Error('Failed to fetch check-ins');
  const data = await res.json();
  return data.checkins;
}

export async function sendChat(
  message: string,
  employeeId: string,
  history: ChatMessage[],
): Promise<{ response: string; tool_calls: { name: string }[]; citations: string[] }> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
    headers: { 'Content-Type': 'application/json' },
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
