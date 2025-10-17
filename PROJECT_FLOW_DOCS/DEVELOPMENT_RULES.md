## 🎯 Core Development Principles

### 1. **Incremental Development**
- Work on **ONE checkbox** from HANDOFF.md at a time
- Each checkbox represents a **small, reviewable unit of work**
- No skipping ahead to future stages
- Complete current stage before moving to next

### 2. **Mandatory Code Review**
- **Every change** requires approval before proceeding
- Even small changes (typos, formatting) need review
- No exceptions to this rule

### 3. **Test-Driven Development (TDD)**
- Write tests **before** or **alongside** implementation
- Every new function needs corresponding tests
- Minimum 80% code coverage required
- Tests must pass before review

### 4. **No Direct Pushes to Main**
- **NEVER push directly to `main` branch** - even for documentation
- **ALL changes** must go through Pull Request workflow
- This includes: code, docs, markdown files, configuration, etc.
- Only exception: Emergency hotfixes (with team lead approval)
- Process: Create branch → Make changes → Push branch → Create PR → Review → Merge