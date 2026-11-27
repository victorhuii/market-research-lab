# Quant portfolio priorities

Assessment: November 27, 2026. Assumed direction: quant development and research infrastructure, based on the requested quant projects. This is a project-selection judgment, not a hiring guarantee. A small set of well-understood projects is more useful on a resume than listing every repository.

## Which projects to feature

| Role direction | Lead projects | What to explain |
| --- | --- | --- |
| Quant developer / trading systems | [Exchange Matching Engine](https://github.com/victorhuii/exchange-matching-engine), [Market Data Replay](https://github.com/victorhuii/market-data-replay), [Walk-Forward Lab](https://github.com/victorhuii/walk-forward-lab) | Correct matching/recovery, binary feed integrity, controlled performance improvements, causal research |
| Quant researcher / research engineer | [Walk-Forward Lab](https://github.com/victorhuii/walk-forward-lab), [Portfolio Risk Engine](https://github.com/victorhuii/portfolio-risk-engine), Exchange Matching Engine | Frozen selection, independent accounting/numerical checks, model failures, uncertainty and execution constraints |
| General backend / systems | Exchange Matching Engine, Market Data Replay, one relevant attributed contribution | State transitions, durability boundaries, bounded input, failure injection, measured tradeoffs |

Do not lead with all three similar research/simulation repos at once. MarketLab remains a useful integrated demonstration, while the newer CLI projects provide deeper, distinct evidence. Optimal Execution Lab is a useful alternative for roles emphasizing numerical optimization or execution research; it adds constrained control and solver validation, while its economic inputs remain hypothetical. Choose the strongest two or three that match the role and that you can explain without reading code during an interview.

The emphasis is consistent with experiment design, time-series data, feature generation and model evaluation in [Jane Street's research role description](https://www.janestreet.com/join-jane-street/position/6302325002/), and data/research engineering in [Citadel Securities' description](https://www.citadelsecurities.com/careers/details/senior-research-engineer-data/). Specific requirements vary by role and level; project evidence does not replace interview preparation or relevant experience.

## Current release evidence

| Repository / Desktop folder | Delivered evidence | Boundary to keep explicit |
| --- | --- | --- |
| [exchange-matching-engine](https://github.com/victorhuii/exchange-matching-engine) | Original C++20 matching/durability, independent Python reference; 22 Python + 3 JS checks; 900-command/90-restart recovery campaign; 24 repeated 10,000-command stress runs across four profiles/two durability modes | Synthetic local benchmarks, no live venue; retained-history memory and longer recovery scaling remain future work |
| [market-data-replay](https://github.com/victorhuii/market-data-replay) | Original C++20 ITCH-subset/MoldUDP64 replay; eleven regression groups, independent reference, sanitizers; 27 injected allocation-failure rollback points; fixed deep-book workload improved 35.2× median | Owned synthetic captures; subset only; no multicast/PCAP/recovery requester; local throughput, not production latency |
| [walk-forward-lab](https://github.com/victorhuii/walk-forward-lab) | Original causal research pipeline; 18 tests; 6,539 aligned official-source observations; protocol/implementation committed before evaluation; 1,757 historical test observations | Revised research baskets, not point-in-time constituents; uncertain advantage, lower Sharpe than equal weight and cost sensitivity; no established live edge |
| [portfolio-risk-engine](https://github.com/victorhuii/portfolio-risk-engine) | Original covariance/tail-risk/attribution library; 16 numerical/causality/workflow tests; 1,760 fixed historical forecast outcomes | All three prespecified VaR models had excessive exceptions; no formal ES backtest, capital certification or nonlinear instrument coverage |
| [optimal-execution-lab](https://github.com/victorhuii/optimal-execution-lab) | Original constrained scheduling model; 12 numerical/workflow tests; objective-gap bounds; analytic/KKT/integer-grid references; 20,000 simulated cash paths per schedule | Hypothetical, uncalibrated inputs; continuous-share relaxation; no claimed market savings |
| [market-research-lab](https://github.com/victorhuii/market-research-lab) | Original causal research/execution simulator and local UI; 17 Python + 3 JS checks | Synthetic demo; simulated fills and operational assumptions |
| [disclosure-radar](https://github.com/victorhuii/disclosure-radar) | Original source-aware delayed-filings workflow; 22 tests | Public disclosures are delayed/partial, not real-time expert purchases; limited sourced sample and official-source environment gaps |
| [echo-canvas-lab](https://github.com/victorhuii/echo-canvas-lab) | Independent acoustics-inspired implementation; 18 JS + 1 Python checks; deterministic geometry and WebAudio lifecycle | Original inspiration credited; browser listening remains unverified in the unavailable browser environment |
| [sentinel-workbench](https://github.com/victorhuii/sentinel-workbench) | Attributed MIT fork extension: local scanner/report workflow; selected 41 Python + 4 JS checks | Do not claim the upstream scanner as original; paid-model/Docker paths were not validated |
| [crossbeam-review](https://github.com/victorhuii/crossbeam-review) | Attributed MIT fork extension: local PDF/text evidence, human gates, draft export; 16 Python + 3 JS checks | Do not claim the upstream project as original; cloud/AI paths remain untested |

Test counts refer to the implemented local scope and selected suites, not exhaustive upstream certification. Each repository contains its own method, limits, evidence and attribution. Desktop folders use the repository name. New quant repos include `docs/PORTFOLIO.md` and PNG/SVG figures ready for website use.

## What is worth improving next

1. **Engine correctness under injected storage faults:** randomized interruption/recovery against the independent reference, retained history memory measurement and snapshot recovery scaling. These add more systems evidence than a new engine dashboard.
2. **Feed integration:** acquire a lawful small real capture or add a precisely documented additional protocol family. Do not label generated fixtures as market data or silently skip unknown messages.
3. **Risk model extension:** prespecify filtered historical simulation or another tail model, evaluate all declared models on a distinct study, and add a genuine ES backtest only with a validated reference. Do not tune until old p-values look attractive.
4. **Research data quality:** a point-in-time universe with delistings and corporate actions would materially improve economic validity. More indicators on the same revised industry data would add less evidence.
5. **External use:** an independently reproduced run, issue report, maintainer review or carefully documented user study adds evidence that another self-authored feature cannot.

The newer releases meet a bounded acceptance bar: core CLI workflow works, key invariants have independent checks, outcomes are reproducible, failures/limits are disclosed, and source attribution is present. None is claimed to be unimprovable.

## Context and credit efficiency

Before changing a repo, read its `AGENTS.md`, scope, and latest status/method document. Work on one concrete numerical or systems gap at a time. Keep synthetic fixtures offline and deterministic; source archives/runtime audits remain ignored. Run focused checks appropriate to the change, then the required release suite once. Use measured reports and implementation-derived diagrams rather than decorative UI or paid image/AI calls.

Use simple lowercase commits and push each completed milestone. Preserve raw benchmark samples and negative findings. Prefer another original project only when it demonstrates a capability absent from the existing portfolio; avoid adding introductory indicator dashboards or forked AI wrappers just to increase repo count.
