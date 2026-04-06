# Claude Code Rules — Menswear BOLO Pipeline

## Code Style

### Section Headings
All files use this exact heading style for section separators:

```python
#=======================================================================
# SECTION TITLE IN ALL CAPS
#=======================================================================
```

The `=` line is exactly 72 characters (including the leading `#`).
Never use the `# ── Title ────` style.

### PEP 8 Line Limits
- **Comments and docstrings**: max 72 characters per line
- **Code**: max 79 characters per line
- Use implicit line continuation inside brackets `()` to wrap long lines

### Docstring Indentation
- Section headings (Assumes, Args, Returns): 4-space indent
- Bullet items under a heading: 4-space indent + `- `
- Bullet continuation lines: 6-space indent (aligns with text after `- `)
- Args continuation lines: 8-space indent

```python
def example(total_transaction: float) -> float:
    """
    One-line summary.

    Assumes:
        - First assumption here
        - Second assumption that is long enough to wrap onto the
          next line like this
    
    Args:
        total_transaction: Item price plus shipping charged
            to the buyer ($).

    Returns:
        Fee as a float rounded to 2 decimal places ($)
    """
```

### Comments
- Always include a space after `#`: `# comment` not `#comment`
- Inline comments: 2 spaces before `#`

## Project Conventions

### Calculator Functions
- All calculator functions are stateless and dependency-free
- Config constants are imported from `config.py` — no magic numbers
- Guard clauses raise `ValueError` for invalid scraper inputs
- All monetary outputs rounded to 2 decimal places

### Testing
- Test classes named `TestFunctionName`
- Test methods named `test_description` (no function name suffix)
- No `__init__` in test classes — pure function tests need no setup
- Calculate expected values manually before asserting — never copy
  output back into the test

### Atomic Commits
- One feature per branch: `feature/<name>`
- One commit per feature once all tests pass
- Only commit files that belong to that feature
