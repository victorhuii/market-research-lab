# Working context

MarketLab is a local Python research workbench and exchange simulator. Read PROJECT_SCOPE.md for acceptance criteria and docs/STATUS.md for current progress.

- Keep the UI plain, readable and concise. No marketing copy or decorative dashboards.
- All demo data and simulated fills must be labeled. Never invent live data, returns or benchmark numbers.
- Match in integer ticks and quantity units. Keep research causal and split by session.
- Preserve deterministic behavior and recovery. Test changes to financial calculations and engine state.
- Run `python3 -m unittest discover -s tests -v` and `node --check web/app.js` before final delivery.
- Use simple lowercase commit messages and push completed feature milestones to origin.
- No paid services, AI API calls or live order execution.
