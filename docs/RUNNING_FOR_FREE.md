# Running the eval for free

Two free routes. Grading is identical for both: the same parser and the same exact graders
as a paid API run. Only the way the answer is obtained differs, and every transcript records which.

| Route | Models | What it costs you | Command |
|---|---|---|---|
| A. OpenRouter `:free` models | open-weight (NVIDIA, Thinking Machines, Google) | $0; 50 requests/day | `run_eval.py --models models.free.yaml --max-cost 0` |
| B. Free chat apps, pasted by hand | frontier models in ChatGPT / Claude.ai / Gemini | $0; ~24 pastes per model | `run_eval.py --new-manual NAME`, then `--import-manual manual/` |

Use A for the "open model" rows; use B for at least one frontier model (the
hackathon checklist asks for one).

---

## Route A: OpenRouter free models

**Limits (OpenRouter, Oct 2026).** 20 requests/minute and **50 requests/day across all free
models** while your lifetime credit purchases are under $10. **Failed attempts count too.** One
model x 8 tasks x 3 trials = 24 requests.

**Once:** `.env` must contain your `OPENROUTER_API_KEY` (never commit it; the hook blocks it).

**Each run:**

```bash
python run_eval.py --models models.free.yaml --trials 1 --max-cost 0 --dry-run      # check the plan (free)
python run_eval.py --models models.free.yaml --trials 1 --max-cost 0 --concurrency 1 --max-attempts 2 --max-requests 45
```

- `--max-cost 0` refuses to run anything that is not `:free`.
- `--max-requests 45` keeps a few of the day's 50 requests spare.
- `--max-attempts 2` limits retries, because every retry uses up the daily quota.
- If OpenRouter says the daily quota is used up, the run **stops by itself**. Finished answers
  are cached, so the next day the same command continues where it stopped.
- A model that OpenRouter refuses, or whose calls fail twice in a row, is **skipped for the
  rest of the run** (its other trials are left for next time), so one broken model cannot use
  up the day's quota.
- To run a single model: add `--model nemotron-3-ultra-free`.

**If something fails** (it is recorded as `API_ERROR`, never as a model failure):
- `404 ... data policy`: in OpenRouter **Settings > Privacy**, allow the free endpoints
  (free providers may log prompts; our prompts are synthetic, so nothing private is sent).
- `404 ... no endpoints` or `model not found`: that free model was withdrawn. Pick another one
  from https://openrouter.ai/models?q=free and edit `models.free.yaml`.
- `403 ... only available on agentic harnesses`: OpenRouter serves that free model only to
  listed apps, not to scripts (this happened to `thinkingmachines/inkling:free`). Replace it.
- `429 ... Provider returned error` (not "per-day"): the model's free provider is busy. Try
  that model again later, e.g. at a different time of day.
- `503 ... overloaded`: same, try again later. Finished answers are cached.
- `TRUNCATED`: the model used its whole `max_tokens` without answering. That *is* a model
  failure (CLAUDE.md rule 8). It is counted and reported separately.

---

## Route B: free chat apps (frontier models)

**1. Create the folder for one app/model** (example name `chatgpt-free`):

```bash
python run_eval.py --new-manual chatgpt-free --trials 3
```

This creates `manual/chatgpt-free/info.yaml`, empty files
`manual/chatgpt-free/task_01/trial_1.txt ... task_08/trial_3.txt`, and
`manual/prompts/task_01.txt ...` (the exact text to paste).

**2. Before chatting:** in the app's settings, turn **off** code execution / data analysis,
web search, file tools, and memory/personalization. Use a temporary or incognito chat if the
app has one. Keep the same model and the same reasoning setting for every trial.

**Faster:** `python scripts/paste_helper.py <name>` does the file handling for steps 3.2-3.4.
It puts the next prompt on the clipboard; you paste it into a new chat and copy the reply, then
press Enter and it saves the reply to the right trial file, unchanged. Trial 1 of every task
comes first. You still use the app by hand: automating a consumer chat app with a bot or
browser agent is against the terms of several of them (e.g. OpenAI's and Anthropic's), and the
hackathon rules require respecting every tool's terms.

**3. For every task and every trial:**
1. Open a **brand-new chat**.
2. Paste the whole content of `manual/prompts/task_XX.txt` as one message.
3. When the answer is complete, copy the **entire reply** with the app's copy button, so the
   final ```` ```json ```` block is kept, along with any explanation the model wrote before it.
4. Paste it into `manual/<name>/task_XX/trial_N.txt` and save. **Never edit it**: no
   retyping, no added or removed spaces. The grader is strict (a space inside a T05 witness
   scores 0, as the prompt says), so the file must be exactly what the model wrote.
5. If the reply visibly ran code or searched the web, discard it and redo the trial in a new chat.

**4. Fill in `manual/<name>/info.yaml`**: app, the model name the app showed, the date, the
reasoning mode, and set `no_tools_confirmed` and `new_chat_per_trial` to `true` only if both are
really true. The import refuses a folder with missing fields.

**5. Grade:**

```bash
python run_eval.py --import-manual manual/
```

Empty trial files are skipped, so you can import after every sitting. Re-importing overwrites
that model's manual transcripts with the current files.

**Honesty notes for the README.** For these rows, say that they were collected through the
free web app on that date; that temperature, reasoning budget and exact model version are
whatever the app used; and that the system prompt was pasted together with the task. Judges
can re-grade them with `--regrade` but cannot re-run them through an API.

---

## Plan that fits the free quota (deadline Nov 9, 10:45 IST)

The pilot on task set v1 is done (`pilot_v1/`) and the tasks were replaced by v2. Every v2 trial
counts, so there is no second calibration round.

| Day | Route A (≤ 45 requests/day) | Route B (any time) |
|---|---|---|
| Nov 1 | Trial 1 for the 3 free models (24 requests) | `--new-manual chatgpt-free --trials 3`; trial 1 of every task (8 pastes) |
| Nov 2 | Trials 2-3 for the model(s) that answered (16 per model) | trials 2-3 (16 pastes) |
| Nov 3-4 | remaining trials + reruns of API errors | optional second app (e.g. another free chat app) |
| Nov 5-8 | analysis, README, video, zip | |

**Status (2026-11-01): ahead of plan.** Route A trials 1-3 are done for Nemotron and Dots
(Gemma's free provider answered HTTP 429 to every call, so it has no valid trial). Route B
trials 1-3 are done for ChatGPT with Think off (2026-11-01) and with Think on (2026-11-02).
Folders for Gemini, DeepSeek (DeepThink on) and Claude.ai are created (`manual/gemini-free/`,
`manual/deepseek-deepthink/`, `manual/claude-free/`) and still empty.

Commit transcripts after each run (`git add transcripts results manual`, then commit). They are
the evidence judges re-grade.
