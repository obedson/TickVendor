export type RecognitionSection = 'achievement-rules' | 'badges' | 'milestones' | 'ranks';
export type Condition = { metric: string; operator: string; threshold: number };
const metrics = new Set(['attendance_count', 'event_participation', 'impact_points', 'task_count', 'contribution_count', 'service_activities', 'leadership_activities', 'peer_confirmations', 'consecutive_activities']);
const rankMetrics = new Set(['attendance_count', 'task_count', 'contribution_count', 'service_activities', 'leadership_activities', 'peer_confirmations', 'badge', 'milestone']);
const operators = new Set(['>=', '<=', '=']);
export function serializeRequirements(section: RecognitionSection, conditions: Condition[]): unknown {
  if (section === 'ranks') return conditions.map(c => ({ requirement_type: c.metric, threshold: c.threshold }));
  if (section === 'milestones') return conditions;
  const leaves = conditions.map(c => ({ metric: c.metric, operator: c.operator, value: c.threshold }));
  return leaves.length === 1 ? leaves[0] : { operator: 'AND', conditions: leaves };
}

/** Reject malformed advanced input before persisting an unusable definition. */
export function validateRequirements(section: RecognitionSection, value: unknown): void {
  const fail = () => { throw Error('Invalid requirements. Use supported metrics, comparisons, and non-negative integer values.'); };
  const number = (value: unknown, min = 0) => typeof value === 'number' && Number.isSafeInteger(value) && value >= min;
  const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
  if (section === 'ranks' || section === 'milestones') {
    if (!Array.isArray(value) || value.length > 20 || (section === 'milestones' && !value.length)) return fail();
    for (const item of value) {
      if (!object(item)) return fail();
      if (section === 'ranks') {
        if (!rankMetrics.has(String(item.requirement_type)) || !number(item.threshold, 1)) return fail();
        if (['badge', 'milestone'].includes(String(item.requirement_type)) && (typeof item.reference_id !== 'string' || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(item.reference_id))) return fail();
      } else if (!metrics.has(String(item.metric)) || !operators.has(String(item.operator)) || !number(item.threshold)) return fail();
    }
    return;
  }
  const tree = (node: unknown, depth: number): void => {
    if (!object(node) || depth > 10) return fail();
    if (node.operator === 'AND' || node.operator === 'OR') {
      if (!Array.isArray(node.conditions) || !node.conditions.length || node.conditions.length > 20) return fail();
      node.conditions.forEach(child => tree(child, depth + 1));
    } else if (!metrics.has(String(node.metric)) || !operators.has(String(node.operator)) || !number(node.value)) return fail();
  };
  tree(value, 0);
}
