import { fireEvent, render, screen } from '@testing-library/react';
import { MissionSummary, RecommendationEvidence } from './DecisionEvidence';

it('separates mandatory stretch budget from preferences and workload', () => {
  render(
    <MissionSummary
      mission={{
        category: 'laptops',
        user_goal: 'Developer laptop',
        hard_constraints: { max_budget_cents: 8500000, min_ram_gb: 32 },
        soft_constraints: { preferred_budget_cents: 7500000, portability: true },
        desired_use_cases: ['software_development'],
        clarification_needed: false,
        clarification_questions: [],
      }}
    />
  );
  expect(screen.getByText('Maximum ₹85,000.00')).toBeInTheDocument();
  expect(screen.getByText('Prefer ₹75,000.00')).toBeInTheDocument();
  expect(screen.getByText('At least 32 GB RAM')).toBeInTheDocument();
  expect(screen.getByText('software development')).toBeInTheDocument();
});

it('shows backend evidence, fit labels and tradeoffs without manufacturing reasons', () => {
  render(
    <RecommendationEvidence
      recommendation={{
        product_id: 'p1',
        overall_score: 91.2,
        constraint_score: 100,
        workload_score: 80,
        preference_score: 90,
        value_score: 76,
        personalization_score: 0,
        labels: ['BEST_FIT', 'BEST_VALUE'],
        reasons: ['32 GB RAM'],
        tradeoffs: ['No published GPU data'],
        penalties: ['Battery data unavailable'],
        evidence: [{ field: 'ram', value: '32 GB', source: 'catalog' }],
      }}
    />
  );
  expect(screen.getByText('91/100 mission fit')).toBeInTheDocument();
  expect(screen.getByText('best fit')).toBeInTheDocument();
  expect(screen.getByText('No published GPU data')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Why this ranking?'));
  expect(screen.getByText('ram: 32 GB · catalog')).toBeInTheDocument();
  expect(screen.queryByText(/excellent battery/i)).not.toBeInTheDocument();
});
