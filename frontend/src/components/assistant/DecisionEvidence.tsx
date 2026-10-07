import { formatInr } from '@/lib/currency';

export type ShoppingMission = {
  category: string | null;
  user_goal: string;
  hard_constraints: {
    max_budget_cents?: number | null;
    min_ram_gb?: number | null;
    max_weight_kg?: number | null;
    required_features?: string[];
    excluded_brands?: string[];
  };
  soft_constraints: {
    preferred_budget_cents?: number | null;
    portability?: boolean;
    professional_design?: boolean;
    preferred_brands?: string[];
  };
  desired_use_cases: string[];
  clarification_needed: boolean;
  clarification_questions: string[];
};

export type Recommendation = {
  product_id: string;
  overall_score: number;
  workload_score: number;
  preference_score: number;
  value_score: number;
  personalization_score: number;
  constraint_score: number;
  labels: string[];
  reasons: string[];
  tradeoffs: string[];
  penalties: string[];
  evidence: { field: string; value: unknown; source: string }[];
};

export type Relaxation = {
  product_id: string;
  violated_constraints: string[];
  message: string;
  requires_confirmation: boolean;
};

export function MissionSummary({ mission }: { mission: ShoppingMission }) {
  const hard = mission.hard_constraints;
  const soft = mission.soft_constraints;
  const requirements = [
    mission.category,
    hard.max_budget_cents != null ? `Maximum ${formatInr(hard.max_budget_cents)}` : null,
    hard.min_ram_gb != null ? `At least ${hard.min_ram_gb} GB RAM` : null,
    hard.max_weight_kg != null ? `At most ${hard.max_weight_kg} kg` : null,
    ...(hard.required_features ?? []),
    ...(hard.excluded_brands ?? []).map((brand) => `Exclude ${brand}`),
  ].filter(Boolean);
  const preferences = [
    soft.preferred_budget_cents != null ? `Prefer ${formatInr(soft.preferred_budget_cents)}` : null,
    soft.portability ? 'Easy to carry' : null,
    soft.professional_design ? 'Professional design' : null,
    ...(soft.preferred_brands ?? []),
    ...mission.desired_use_cases.map((item) => item.replace(/_/g, ' ')),
  ].filter(Boolean);
  return (
    <div
      role="group"
      aria-label="Shopping mission"
      className="rounded-xl border border-accent-100 bg-accent-50 p-4 text-sm text-ink-800"
    >
      <h3 className="font-semibold">Your shopping mission</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <p className="font-medium">Must meet</p>
          <ul className="mt-1 space-y-1">
            {requirements.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        {preferences.length > 0 && (
          <div>
            <p className="font-medium">Preferences</p>
            <ul className="mt-1 space-y-1">
              {preferences.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {mission.clarification_needed &&
        mission.clarification_questions.slice(0, 1).map((question) => (
          <p key={question} className="mt-3 font-semibold">
            {question}
          </p>
        ))}
    </div>
  );
}

export function RecommendationEvidence({ recommendation }: { recommendation: Recommendation }) {
  return (
    <div
      role="group"
      aria-label="Recommendation evidence"
      className="mt-3 space-y-3 text-sm text-ink-700"
    >
      <div className="flex flex-wrap gap-2">
        {recommendation.labels.map((label) => (
          <span
            key={label}
            className="rounded-full bg-accent-50 px-3 py-1 font-semibold text-accent-800"
          >
            {label.replace(/_/g, ' ').toLowerCase()}
          </span>
        ))}
      </div>
      <p className="font-semibold text-ink-900">
        {Math.round(recommendation.overall_score)}/100 mission fit
      </p>
      {recommendation.reasons.length > 0 && (
        <div>
          <h4 className="font-semibold">Why it fits</h4>
          <ul className="mt-1 list-inside list-disc space-y-1">
            {recommendation.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}
      {recommendation.tradeoffs.length > 0 && (
        <div>
          <h4 className="font-semibold">Trade-offs</h4>
          <ul className="mt-1 list-inside list-disc space-y-1">
            {recommendation.tradeoffs.map((tradeoff) => (
              <li key={tradeoff}>{tradeoff}</li>
            ))}
          </ul>
        </div>
      )}
      <details className="rounded-lg border border-ink-200 p-3">
        <summary className="cursor-pointer font-semibold">Why this ranking?</summary>
        <p className="mt-2 text-xs">Scores reflect this mission and published catalog data.</p>
        <dl className="mt-2 grid grid-cols-2 gap-2 text-xs">
          {[
            ['Workload', recommendation.workload_score],
            ['Preferences', recommendation.preference_score],
            ['Value', recommendation.value_score],
            ['Personalization', recommendation.personalization_score],
          ].map(([label, score]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{Math.round(Number(score))}/100</dd>
            </div>
          ))}
        </dl>
        <ul className="mt-3 space-y-1 text-xs">
          {recommendation.evidence.map((item, index) => (
            <li key={`${item.field}-${index}`}>
              {item.field.replace(/_/g, ' ')}:{' '}
              {typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value)} ·{' '}
              {item.source}
            </li>
          ))}
        </ul>
        {recommendation.penalties.map((penalty) => (
          <p key={penalty} className="mt-2 text-xs">
            {penalty}
          </p>
        ))}
      </details>
    </div>
  );
}
