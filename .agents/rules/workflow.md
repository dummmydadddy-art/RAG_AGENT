# Workflow Discipline Rule

This rule governs intake, planning, task execution, and escalation across `/gsd` and `/team` modes.

## 1. Intake & Retrieval
1. Restate the objective and acceptance criteria explicitly.
2. Before formulating any plan or architecture, execute `rag_search` against the `knowledge` and `lessons` collections.
3. Extract up to 5 relevant lessons and explicitly cite their IDs (`L-YYYY-MM-XXXX`) in the plan.
4. If essential domain requirements or interfaces are ambiguous, stop and request clarification. State non-blocking assumptions explicitly.

## 2. Planning Protocol
1. Create a detailed implementation plan artifact before writing or modifying any implementation code.
2. Slicing: Decompose the work into discrete, test-verifiable tasks.
3. Risk Assessment: Assign a risk score (Low, Medium, High).
4. If the feature touches physical or mathematical concepts, the PhysMath Verifier must formulate acceptance checks from the specification before code authoring begins.

## 3. Escalation to `/team` Mode
A `/gsd` single-lead execution must escalate to `/team` mode when:
- 3 or more distinct architectural modules are modified simultaneously.
- An implementation task fails automated verification twice consecutively.
- Mathematical or physical derivations are contested or produce conflicting symbolic formulations.
- The reviewer identifies security or architectural boundary violations requiring independent debate.
