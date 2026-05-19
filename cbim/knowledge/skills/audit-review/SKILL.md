# Skill: Adversarial Review (Auditor)

## Execution Steps

When invoked, the caller should provide in the prompt:
- Review target (module name / task name)
- Review type (design review / code review / governance review)
- Target agent id
- Relevant file paths

Execute:

1. **Load review context**
   - Module knowledge pack `<module-dir>/.dna/module.md` (+ `contract.md` if present)
   - Architecture principles: the "Beliefs" and "Architecture Principles (C1-C6)" sections from `.claude/agents/architect.md`
   - Target agent's professional standards: the responsibilities/principles section from `.claude/agents/<agent-id>.md`
2. Knowledge layer review
3. Scan code (Glob + Grep + Read)
4. Code layer item-by-item scoring
5. Five-dimension review
6. Hallucination detection
7. **Output review report** (return directly to caller; do not write to files)

---

## Two-Layer Review

| Layer | Review Target | What to Find |
|-------|--------------|-------------|
| **Knowledge layer** | module.md (+ contract.md if present) | Whether design decisions are sound; any blind spots |
| **Code layer** | Physical workspace source code | Implementation quality + LLM hallucinations + logic flaws |

Knowledge layer review comes first — if the blueprint is flawed, perfect code is still wrong.

---

## Five-Dimension Review

### Dimension 1: Technical Decision Critique

**Knowledge layer:**
- Does the design decision actually solve the real problem? Are there simpler alternatives?
- Are the implicit assumptions valid? Is the dependency direction sound?
- Does the module split granularity match actual complexity?
- Hallucination detection: do the APIs / patterns / dependencies referenced in the design actually exist?

**Code layer:** score each item PASS=1 / WARN=0.5 / FAIL=0, each with file:line

### Dimension 2: User Experience

- Is the API naming intuitive? Is the parameter order natural?
- How much internal detail does the consumer need to know?
- Do error scenarios produce meaningful feedback?

### Dimension 3: Logic Flaws

- Concurrency safety, resource leaks, null references, boundary conditions

### Dimension 4: Testability

- Are dependencies replaceable? Are there missing state transition paths?

### Dimension 5: Progress and Complexity

- How long will this design take to implement? Is there a simpler approach?
- Is this over-designed for imagined requirements? Are modules split too finely?
- How many iterations does the target agent need? Is phased delivery possible?

---

## Adversarial Review Threshold (Security-Related Code)

**Scope**: Any code that handles untrusted external input — path validation / access control / injection defense / deserialization / encryption / authentication.

---

## Hallucination Detection

### Code-Layer Hallucinations
- Fake implementations (empty methods / TODOs)
- Ghost dependencies (using non-existent namespaces)
- Extraneous artifacts (types not designed in the knowledge)
- Signature drift (actual vs contract.md / module.md class diagram)
- Dead code (unreferenced public types)

### LLM-Specific Hallucinations
- Fabricated APIs: referencing methods or parameters that don't exist in the framework/library
- Fabricated patterns: claiming to use a design pattern but implementation doesn't match
- Fabricated constraints: claiming "must do it this way" with no real technical reason
- Self-consistent hallucinations: module.md is internally consistent but misaligns with code reality
- Concept drift: the same term has different meanings across documents

---

## Critique Method for the Architect

**Independent reasoning:** Do not accept "the architect said so, therefore correct." Rederive from first principles: what is the problem? What are the constraints? Is this the only sound approach?

**Challenge assumptions:** Identify the implicit assumptions in the design; question each one. "You assume X always holds — what if it doesn't?"

**Alternative solutions:** For each key decision, construct at least one alternative. If the alternative is simpler and satisfies requirements, the original needs stronger justification.

**LLM bias counter:** Typical mistakes LLMs (as architect) make:
- Pattern matching: sees A resembles B, applies B's approach, ignores A's unique constraints
- Over-abstraction: tendency toward multiple layers of encapsulation, preemptive extension points, rather than the simplest implementation
- Consistency preference: adding unnecessary structure for "symmetry" or "uniformity"
- Authority citation: referencing non-existent APIs, framework features, design patterns

---

## Report Format

```
## <module/task name> Review Report

### Total Score
Knowledge layer / Code layer percentages

### Knowledge Layer Score | Code Layer Score
### User Experience | Logic Flaws | Testability
### Hallucination Detection
### Progress Assessment
### Challenges to Target Agent (if any)
### FAIL Items Summary (change checklist)

### Conclusion
PASS — ready for next step / FAIL — requires revision before re-review
```
