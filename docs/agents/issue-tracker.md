# Issue tracker: GitHub

Issues and specifications for this repository live in GitHub Issues for `CDSE-JairoSB/rpa-robot-framework`. Use the `gh` CLI for issue operations.

## Conventions

- **Create an issue:** `gh issue create --repo CDSE-JairoSB/rpa-robot-framework --title "..." --body "..."`
- **Read an issue:** `gh issue view <number> --repo CDSE-JairoSB/rpa-robot-framework`
- **List issues:** `gh issue list --repo CDSE-JairoSB/rpa-robot-framework`
- **Update an issue:** `gh issue edit <number> --repo CDSE-JairoSB/rpa-robot-framework`
- **Close an issue:** `gh issue close <number> --repo CDSE-JairoSB/rpa-robot-framework`
- Use Markdown issue bodies with enough context for another agent or maintainer to act without reconstructing the conversation.

## Pull requests

Pull requests are the normal code-review surface for changes. Use `gh pr create`, `gh pr view`, and `gh pr list` when the workflow requires pull-request operations. Pull requests are not treated as triage issues unless explicitly requested.

## Wayfinding operations

When a skill needs to preserve a codebase map or implementation plan, keep that material in the repository documentation or the relevant GitHub issue/PR. Link related issues and pull requests rather than duplicating long descriptions.

## Repository

- **Remote:** `https://github.com/CDSE-JairoSB/rpa-robot-framework.git`
- **Tracker:** GitHub Issues
- **CLI:** `gh`
