# Agent Workflow

## Authority

GitHub Issues, pull requests, commits, reviews, and Actions runs are the durable record. Chat history and agent memory are not authorization or task state. Human approval of a plan does not authorize implementation, publication, merge, or deployment unless that permission is stated separately.

The standing agent roles are exactly Planner, Engineer, and CI / Build-Fix. The human maintainer owns task approval, publication authorization, review, merge, and deployment decisions. No agent may merge, deploy, alter branch protection, or bypass required CI.

## Lifecycle

1. A human approves the Issue objective and risk.
2. Planner inspects the repository and available GitHub context, then proposes task contracts, dependencies, parallelism, acceptance criteria, validation, risks, branch names, and baseline SHA. Planner is read-only; a human approves the plan.
3. Each approved task is assigned one Engineer, worktree, feature-oriented branch, and Issue contract. The Engineer verifies the approved base SHA and scope before editing, adds or updates tests, runs required checks, and reports evidence.
4. Commit/push and PR creation happen only as explicitly authorized by the Issue contract or separate human approval. Never work directly on `main`.
5. GitHub Actions on the current PR head is authoritative. A failure goes to CI / Build-Fix for evidence-based diagnosis. Repair is disabled unless explicitly authorized for that task and branch.
6. During repair, the Engineer pauses writes. Build-Fix verifies the run's PR and current head SHA, works only on the same feature branch, stays within the approved scope and retry budget, and confirms new CI runs on the repaired SHA. Ambiguous, stale, sensitive, or out-of-scope failures are escalated.
7. A human reviews the final diff and current checks, then alone approves merge. Deployment/release requires a separate human decision.

## Worktrees and Parallelism

Use one worktree and task branch per independent Issue, based on a human-approved SHA. A worktree is Git isolation, not a security boundary. It does not isolate credentials, databases, ports, networks, or GitHub permissions; never add production secrets or `.env` files.

Parallel work requires independent acceptance criteria, stable contracts, non-overlapping files, isolated resources, and no shared migration, schema, CI, dependency, security-core, or fixture ownership. Serialize tasks that share those surfaces. Never allow two writers on the same branch/worktree; pause the Engineer while Build-Fix repairs that branch.

## Repair Limit and Escalation

Proposed maximum: two repair commits per task, tracked durably outside chat. Do not enable automatic retries until attempt tracking, duplicate suppression, stale-SHA checks, and CI re-triggering are validated. If the ledger is not reliable, allow at most one attempt per explicit authorization and require human reauthorization for another. CI remains authoritative; no repair may disable tests or weaken checks.

GitHub Agentic Workflows (`gh-aw`) is a candidate for failure-triggered automation, but remains a preview capability and must be piloted. Begin with read-only diagnosis. Its same-PR safe output and the credential needed to trigger follow-up CI require validation in the target repository. Keep write credentials out of the agent execution context and do not execute untrusted PR code in privileged workflows.

## Status Reporting

Every handoff records the Issue/PR, role, status, branch, baseline and current SHA, changed files, acceptance criteria, exact checks and results, failures and evidence, repair attempt count, risks, blockers, authorization state, and next owner. Missing evidence or permission means stop and ask the human.