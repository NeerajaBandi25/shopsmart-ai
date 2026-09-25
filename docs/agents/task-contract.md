# Engineering Task Contract

Use one contract per independently reviewable Issue. The Issue form is a starting point; the human maintainer confirms the fields before implementation.

## Required Before Implementation

- **Objective:** observable result and reason.
- **Acceptance criteria:** verifiable outcomes and their evidence.
- **Scope:** included behavior and allowed paths/modules.
- **Non-goals:** adjacent work explicitly excluded.
- **Dependencies:** prerequisite Issues, interfaces, shared files, and sequencing.
- **Risk:** low, medium, high, or critical, with rationale.
- **Security impact:** authentication, authorization, data, secrets, threat model, and security-check effects.
- **Migration impact:** schema/data changes or an explicit assessment that none are identified.
- **Validation:** tests, exact commands, required CI checks, and known environment prerequisites.
- **Risks and rollback:** failure modes, mitigations, and reversal plan.
- **Baseline SHA:** human-selected commit from which the task worktree starts.
- **Branch:** task-oriented branch name; never an agent name and never `main`.
- **Allowed/prohibited paths:** explicit enough to identify shared or protected surfaces.
- **Publication authorization:** explicitly state commit, push, and PR creation permission and target branch. Blank or ambiguous means not authorized.
- **Build-Fix authorization:** default none. If granted, state eligible failure classes, permitted paths, same-branch requirement, attempt budget, and escalation conditions.

## Engineer Completion Evidence

The Engineer reports the Issue, branch, baseline/final SHA, changed files, acceptance mapping, exact commands/results, checks not run, security/migration impact, known limitations, risks, blockers, and whether publication was authorized and performed. Never claim a check passed unless it ran and passed.

## CI / Build-Fix Evidence

Build-Fix reports the workflow run and URL/ID, job/step, relevant log evidence, associated Issue/PR, failed-run SHA, verified current PR head SHA, classification/confidence, changed files, local validation, repair commit/push status, attempt count and durable evidence, and fresh CI run/SHA. If PR identity, current SHA, authorization, or attempt state cannot be verified, it must not write.

## Human Decisions

The human approves the Issue and plan, baseline and parallel launch, publication where required, Build-Fix write permission, final review, merge, and deployment/release. Neither passing CI nor approval of an earlier stage grants later-stage permission.