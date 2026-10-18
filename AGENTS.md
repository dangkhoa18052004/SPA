
# Codex Project Instructions

## General
- Read only files relevant to the current task.
- Search for symbols and file paths before opening files.
- Do not scan the entire repository unless necessary.
- Reuse existing components, utilities and design patterns.
- Prefer minimal, targeted changes.
- Avoid unnecessary dependencies and refactoring.

## Browser Testing
- Prefer Playwright CLI for browser automation.
- Use browser snapshots only when necessary.
- Inspect console errors and failed requests.
- Take screenshots for visual defects.
- Verify changes after editing.

## Token Efficiency
- Keep tool output concise.
- Avoid printing entire large files.
- Avoid repeatedly reading unchanged files.
- Do not repeat completed analysis.
- Summarize findings and reference relevant paths.
- Split large tasks into smaller independent tasks.

## Safety
- Do not modify database schemas without approval.
- Do not change production configuration without approval.
- Do not expose credentials or environment secrets.
- Do not deploy without approval.

## Completion
- Report changed files.
- Report tests executed and their results.
- Distinguish verified fixes from untested changes.
