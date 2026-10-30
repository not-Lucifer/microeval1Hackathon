# micro1 Eval Hackathon — Condensed Brief

> Condensed from the official "Find What AI Can't Do Yet — Participant's Guide". Put this file at `docs/HACKATHON_BRIEF.md` so Claude Code always has the judging context. The official Instructions tab (published at kickoff) overrides anything here.

## 1. Goal
Find a real limitation of frontier AI models in a field the author knows well, and turn it into a **rigorous, reproducible eval**. No agent needs to be built. The deliverable is the *measurement*.

Four questions every submission must answer:
1. Where does AI fall short in the author's field? (real, practical limitation)
2. Would two experts agree on the right answer? (clear tasks, defensible result)
3. Does the grader judge reliably? (no false passes, no false fails)
4. Can someone else reproduce the results from a clean environment using the README?

## 2. Key dates

| Milestone | GMT | IST (author's timezone) |
|---|---|---|
| Challenge opens | Oct 30, 07:15 | Oct 30, 12:45 |
| **Submissions close** | **Nov 9, 05:15** | **Nov 9, 10:45 AM** |
| Winners announced | Nov 23, 2026 | Nov 23, 2026 |

(PT deadline is Nov 8, 9:15 PM.) Internal target: submit by **Nov 8 evening IST**.

## 3. What gets submitted (via HackerRank event page)
1. **ZIP** (≤ 50 MB; code and small supporting files only; **no videos**; must include a README).
2. **Video link** (≤ 5 min; must open without requesting permission; audio must play; AI voice is fine).
3. **Short written description**: domain, limitation, number of tasks, models tested, headline finding.

## 4. Vocabulary
| Term | Meaning |
|---|---|
| Task | One test case with defined input and success criteria (aim for ~5–10) |
| Trial | One model attempt at one task (run several, 3–5 is a good start) |
| Grader | Logic that scores an attempt |
| Reference solution | Known-correct answer that passes all graders; proves solvability and that the grader works |
| Transcript | Full record of a trial (prompt, output, reasoning) |
| Outcome | The final checked result (grade the result, not the path) |
| Harness | Code that runs tasks, collects transcripts, applies graders, aggregates results |
| pass@k | Succeeded at least once in k tries |
| pass^k | Succeeded in **every** one of k tries (consistency) |

## 5. What makes a strong eval
- Targets a limitation a practitioner would care about; the author can explain *why it is hard before running any model*.
- Tasks are clear: two independent experts reach the same verdict. **Everything the grader checks is stated in the prompt.**
- Every task has a reference solution that passes the grader. Deliberately wrong answers fail it.
- Prefer code-based graders (fast, objective, reproducible). LLM judges only with specific rubric items, a different judge model, an "UNKNOWN" escape, and calibration against hand grading.
- Grade the outcome, not the steps. Use partial credit where sensible.
- Models fail for real reasons: a 0% pass rate everywhere is a warning sign (broken task/grader); ~100% means no headroom; stronger models / more reasoning should generally do better. Do not pick tasks only because one model failed them.
- Multiple trials, variance reported, clean state per trial, model names/versions/settings/dates/cost/runtime recorded.
- Cannot be gamed: reference answers are never visible to the model; outputs can't pass by accident.
- **The author has read the failing transcripts** and can say whether the model or the grader was wrong.
- **A human expert built and checked everything.** AI tools are allowed, but the README must say which parts AI drafted and how they were reviewed. Judges penalize generic tasks, unverified reference answers, rubric/task mismatches, and filler.

## 6. Weak vs strong (quick reference)
| Weak | Strong |
|---|---|
| Trick questions, riddles, letter counting | Realistic tasks a professional would face |
| "The model got it wrong" | "The model fails because it doesn't account for X when Y" |
| Correct answer is opinion | Two experts agree on the verdict |
| Grader checks things the prompt never mentioned | Everything graded is stated in the task |
| One run, one number | Multiple trials, variance reported |
| Grader never tested on a correct answer | Reference solution passes every grader |
| Grades steps | Grades result |
| 0% everywhere | Spread across models, failures explained |
| Confidential/unlicensed data | Public, synthetic or licensed data |
| Runs only on author's machine | Judges can reproduce from README |
| Unreviewed AI output | Author wrote or checked every task and answer |

## 7. Judging rubric (100 points)
| Criterion | Pts | Strong work looks like | Self-check |
|---|---|---|---|
| Real-world relevance | 15 | Limitation matters in practice; README says who relies on this work and what failure costs | Would a practitioner care? |
| Task design | 20 | Realistic, clear, unambiguous; defensible answer; reference solution; grader checks only what the prompt states | Would two experts reach the same verdict? |
| Grader reliability | 20 | No false passes/fails; accepts every reference; rejects deliberately wrong answers; any LLM judge is calibrated | Tested on right *and* wrong answers, not just model outputs? |
| Evidence of model limitations | 15 | Frontier models, several trials, clear spread, transcripts back every failure explanation | Can I show *why* they fail? |
| Reproducibility | 15 | Judge can run it from clean env via README; commands, deps, versions, data, runtime, cost documented | Could someone reproduce without asking me? |
| Human expertise & review | 10 | Tasks, answers, grading rules show author's expertise and were checked by the author; README discloses AI use | Did I check every task, answer, rule myself? |
| Insight / hot take | 5 | Observed failure → clear lesson about where AI falls short and what closes the gap | What did I learn that I didn't expect? |

Scoring happens only after eligibility, completeness, integrity and reproducibility checks pass.

## 8. Suggested ZIP layout (official format at kickoff takes priority)
```
README.md  tasks/  reference/  graders/  run_eval.py  requirements.txt
results/  transcripts/  .env.example   (names only, NEVER real keys)
```

## 9. README must cover
What it tests · who it's for / why it matters · task overview · grading + how the grader was validated · how to run (commands, versions, env vars) · results table (models with versions/settings, trials per task, pass rate, pass^k, cost) · per-task failure notes with transcript links (at least one failure per task, and at least one task where models came close) · cost & runtime · provenance (data, licences, what pre-existed vs built during the hackathon) · main failure mode & hot take · AI use disclosure.

Results table format:

| Model (version, settings) | Trials/task | Pass rate | pass^k | Cost per full run |
|---|---|---|---|---|

## 10. Ground rules
1. One eval, built individually, original work for this event.
2. Building on earlier tools/work is fine — state clearly what pre-existed.
3. Adapting tasks/ideas from an existing benchmark must be disclosed (undisclosed copying = cheating).
4. Only public/synthetic/licensed data. No confidential or private data.
5. Respect licences and ToS of every tool, model, dataset.
6. No API keys or credentials in the submission.
7. Report results honestly; every claim backed by submitted results and transcripts.
8. Give judges what they need to reproduce the main result in a clean environment.
9. AI tools allowed; author is responsible for correctness of everything submitted.

## 11. Pre-submission checklist
- [ ] Every task has a reference solution that passes its grader
- [ ] Deliberately wrong answers fail the grader
- [ ] Everything the grader checks is stated in the task
- [ ] ≥ 1 frontier model tested, multiple trials per task
- [ ] I've read the failing transcripts and can explain why models fail
- [ ] README explains run/reproduce, including versions, cost and runtime
- [ ] ZIP opens, < 50 MB, no videos
- [ ] No API keys, passwords, confidential or private data anywhere in the ZIP
- [ ] Prior work (if any) clearly disclosed
- [ ] Video link opens without permission and plays with audio
- [ ] Description filled in
- [ ] Representative transcripts included for every model reported
- [ ] I've scored my own project against the rubric
- [ ] I've reviewed every task, reference answer and grading rule myself

Contact: hackathon@micro1.ai · Further reading: Anthropic "Demystifying evals for AI agents"; Lance Martin "Automating eval design and hillclimbing with Claude".
