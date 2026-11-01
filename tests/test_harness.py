"""End-to-end harness tests with a fake client: no network, no API key."""
import asyncio
import json
from types import SimpleNamespace

import openai
import pytest

import run_eval
from graders.grader import load_reference
from harness import client as client_module
from harness.cache import ResponseCache
from harness.client import STOP_FREE_DAILY, STOP_NO_CREDITS, CompletionResult, ModelSpec, OpenRouterClient
from harness.cost import CostTracker, estimate, settings_key
from harness.metrics import (
    failure_note,
    listed_examples_missed,
    load_transcripts,
    render_markdown,
    split_stale,
    summarize,
)
from harness.parsing import extract_final_json
from harness.prompts import load_tasks, tasks_by_id
from harness.runner import run_trials

# --------------------------------------------------------------------------- parsing


def fenced(obj) -> str:
    return "```json\n" + json.dumps(obj) + "\n```"


def test_last_json_block_wins():
    text = "first try\n" + fenced({"witness": "a"}) + "\nno wait\n" + fenced({"witness": "b"})
    assert extract_final_json(text) == ({"witness": "b"}, None)


def test_invalid_last_block_is_an_error_even_if_an_earlier_one_is_valid():
    text = fenced({"witness": "a"}) + "\n```json\n{oops}\n```"
    value, error = extract_final_json(text)
    assert value is None and "not valid JSON" in error


def test_fallback_to_last_top_level_object():
    text = 'Answer: {"start": "S", "productions": [{"lhs": "S", "rhs": ["a"]}]} done'
    assert extract_final_json(text)[0] == {"start": "S", "productions": [{"lhs": "S", "rhs": ["a"]}]}


def test_no_json_at_all():
    assert extract_final_json("I think the answer is 42.")[0] is None


def test_uppercase_fence_and_trailing_text():
    assert extract_final_json("```JSON\n{\"witness\": \"ab\"}\n```\nThanks!") == ({"witness": "ab"}, None)


# --------------------------------------------------------------------------- runner


class FakeClient:
    """Returns canned replies keyed by (model name, task id); each key holds a list that is
    consumed in trial order (concurrency=1 keeps the order deterministic)."""

    def __init__(self, replies: dict):
        self.replies = {k: list(v) for k, v in replies.items()}
        self.calls: list[tuple[str, list]] = []

    async def complete(self, spec, messages):
        self.calls.append((spec.name, messages))
        task_id = next(t["id"] for t in load_tasks() if t["prompt"] == messages[1]["content"])
        return self.replies[(spec.name, task_id)].pop(0)


def ok(answer, cost=0.01) -> CompletionResult:
    return CompletionResult(text="reasoning...\n" + fenced(answer), finish_reason="stop",
                            usage={"prompt_tokens": 100, "completion_tokens": 50, "cost_usd": cost})


GOOD, BAD = ModelSpec(name="good-model", openrouter_id="x/good"), ModelSpec(name="bad-model", openrouter_id="x/bad")


def scripted_replies():
    ref1, ref5 = load_reference("task_01")["answer"], load_reference("task_05")["answer"]
    return {
        ("good-model", "task_01"): [ok(ref1), ok(ref1)],
        ("good-model", "task_05"): [ok(ref5), ok(ref5)],
        ("bad-model", "task_01"): [
            CompletionResult(text="```json\n{\"states\": [", finish_reason="length", usage={"cost_usd": 0.02}),
            CompletionResult(text="no idea", finish_reason="stop", usage={"cost_usd": 0.01}),
        ],
        ("bad-model", "task_05"): [
            CompletionResult(error="RateLimitError: 429"),
            ok({"witness": "ab"}),
        ],
    }


def run(tmp_path, client, cost=None, cache_enabled=True):
    tasks = load_tasks(["task_01", "task_05"])
    return asyncio.run(run_trials(tasks, [GOOD, BAD], 2, client, tmp_path / "transcripts",
                                  ResponseCache(tmp_path / "cache", cache_enabled), cost or CostTracker(), 1,
                                  log=lambda *_: None))


def test_end_to_end_grades_and_metrics(tmp_path):
    client = FakeClient(scripted_replies())
    run(tmp_path, client)
    transcripts = load_transcripts(tmp_path / "transcripts")
    assert len(transcripts) == 8
    codes = {(t["model"], t["task_id"], t["trial"]): t["grade"]["failure_code"] for t in transcripts}
    assert codes[("bad-model", "task_01", 1)] == "TRUNCATED"
    assert codes[("bad-model", "task_01", 2)] == "PARSE_ERROR"
    assert codes[("bad-model", "task_05", 1)] == "API_ERROR"
    assert codes[("bad-model", "task_05", 2)] == "WITNESS_NOT_DISTINGUISHING"
    assert all(codes[("good-model", t, k)] is None for t in ("task_01", "task_05") for k in (1, 2))

    card = summarize(transcripts)
    good, bad = card["models"]["good-model"], card["models"]["bad-model"]
    assert (good["pass_rate"], good["pass_at_k"], good["pass_hat_k"]) == (1.0, 1.0, 1.0)
    assert bad["valid_trials"] == 3 and bad["api_errors"] == ["task_05/trial_1"]
    assert (bad["pass_rate"], bad["truncated"]) == (0.0, 1)
    md = render_markdown(card)
    assert "good-model" in md
    assert "| bad-model | task_05 | 2 | 0.0 | WITNESS_NOT_DISTINGUISHING | `ab` is in neither language |  |" in md
    assert [f["task_id"] for f in bad["failures"]] == ["task_01", "task_01", "task_05"] and good["failures"] == []
    # every transcript stores what a judge needs
    t = transcripts[0]
    for key in ("prompt", "system_prompt", "raw_output", "settings", "date", "usage", "grade", "finish_reason"):
        assert key in t


@pytest.mark.parametrize("code, cex, details, expected", [
    ("NOT_EQUIVALENT", "100", {"model_accepts": True}, "accepts `100`, which is not in L"),
    ("NOT_EQUIVALENT", "", {"model_accepts": False}, "rejects `ε`, which is in L"),
    ("NON_MINIMAL_STATE_BLOAT", None, {"states_given": 84, "states_minimal": 14},
     "right language, but 84 states (minimal: 14)"),
    ("INCOMPLETE_DFA", None, {"n_missing_transitions": 2}, "2 missing transitions"),
    ("INCOMPLETE_DFA", "ab", {"n_missing_transitions": 1},
     "1 missing transition; even with a trap state added it is wrong on `ab`"),
    ("WITNESS_NOT_DISTINGUISHING", "abab", {"witness": "", "accepted_by_both": False}, "`ε` is in neither language"),
    ("WITNESS_NOT_SHORTEST", "abab", {"witness_length": 18, "shortest_length": 16},
     "distinguishes, but has length 18 (shortest: 16)"),
    ("OVERGENERATES", "[]", {}, "generates `[]`, which is not in L"),
    ("UNDERGENERATES", "aba", {}, "cannot generate `aba`, which is in L"),
    ("CNF_VIOLATION", None, {"violations": ["S -> a R1 (terminal in a binary rule)"]},
     "not in CNF: S -> a R1 (terminal in a binary rule)"),
    ("TRUNCATED", None, {"finish_reason": "length"}, "no final answer within 64000 output tokens"),
    ("PARSE_ERROR", None, {"error": "no JSON object found"}, "no JSON object found"),
])
def test_failure_note_says_what_was_wrong(code, cex, details, expected):
    t = {"grade": {"failure_code": code, "counterexample": cex, "details": details, "score": 0.0},
         "usage": {"completion_tokens": 64000}}
    assert failure_note(t) == expected


def test_listed_examples_missed_checks_the_answer_against_its_own_prompt():
    tasks = tasks_by_id()
    accept_all = {"states": ["q"], "start": "q", "accepting": ["q"], "transitions": {"q": {"0": "q", "1": "q"}}}
    t01 = {"grade": {"failure_code": "NOT_EQUIVALENT"}, "parsed_answer": accept_all}
    assert listed_examples_missed(t01, tasks["task_01"]) == [
        f"`{w}` (listed not in L)" for w in tasks["task_01"]["examples"]["out"]]
    grammar = load_reference("task_07")["answer"]
    over = {**grammar, "productions": grammar["productions"] + [{"lhs": "Ev", "rhs": ["LB", "RB"]}]}
    t07 = {"grade": {"failure_code": "OVERGENERATES"}, "parsed_answer": over}
    # Ev -> [ ] makes "[]" a word, and also a (-group's content: ( Ev ) gives "([])"
    assert listed_examples_missed(t07, tasks["task_07"]) == ["`[]` (listed not in L)", "`([])` (listed not in L)"]
    # right language, a task without listed examples, or no parsed answer: not applicable
    assert listed_examples_missed({"grade": {"failure_code": "NON_MINIMAL_STATE_BLOAT"}}, tasks["task_01"]) is None
    assert listed_examples_missed({"grade": {"failure_code": "NOT_EQUIVALENT"}, "parsed_answer": accept_all},
                                  tasks["task_03"]) is None
    assert listed_examples_missed({"grade": {"failure_code": "TRUNCATED"}}, tasks["task_08"]) is None


def test_cache_avoids_repeat_calls_but_not_api_errors(tmp_path):
    client = FakeClient(scripted_replies())
    run(tmp_path, client)
    assert len(client.calls) == 8
    retry = FakeClient({("bad-model", "task_05"): [ok(load_reference("task_05")["answer"])]})
    run(tmp_path, retry)
    assert [c[0] for c in retry.calls] == ["bad-model"]  # only the API_ERROR trial was retried


def test_replaying_cached_answers_keeps_the_date_they_were_given(tmp_path):
    """A later run (e.g. --trials 3 after --trials 2) replays finished trials from the cache; their
    transcripts must keep the date the model answered, not the date of the replay."""
    run(tmp_path, FakeClient(scripted_replies()))
    earlier = "2000-01-01T00:00:00+00:00"
    paths = sorted((tmp_path / "transcripts").rglob("trial_*.json"))
    for p in paths:
        p.write_text(json.dumps({**json.loads(p.read_text(encoding="utf-8")), "date": earlier}), encoding="utf-8")
    run(tmp_path, FakeClient({("bad-model", "task_05"): [CompletionResult(error="RateLimitError: 429")]}))
    dates = {p.relative_to(tmp_path).as_posix(): json.loads(p.read_text(encoding="utf-8"))["date"] for p in paths}
    retried = "transcripts/bad-model/task_05/trial_1.json"  # API errors are never cached: a new call
    assert dates.pop(retried) != earlier and set(dates.values()) == {earlier}


def test_max_cost_stops_new_calls(tmp_path):
    client = FakeClient(scripted_replies())
    spent = CostTracker(max_usd=0.01)
    spent.add(0.02)
    run(tmp_path, client, cost=spent)
    assert client.calls == []


def test_max_cost_zero_allows_free_calls(tmp_path):
    client = FakeClient(scripted_replies())
    run(tmp_path, client, cost=CostTracker(max_usd=0.0))  # free calls report $0... (these fakes cost $0.01)
    assert len(client.calls) == 1  # ...and the first charged call stops the run


def test_regrade_reproduces_stored_grades(tmp_path):
    run(tmp_path, FakeClient(scripted_replies()))
    assert run_eval.regrade(tmp_path / "transcripts", write=False, results_dir=tmp_path / "results") == 0
    assert (tmp_path / "results" / "summary.md").exists()
    # tamper with one stored grade: regrade must notice
    path = next((tmp_path / "transcripts").rglob("trial_1.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["grade"]["failure_code"] != "API_ERROR":
        data["grade"]["score"] = 0.123
        path.write_text(json.dumps(data), encoding="utf-8")
        assert run_eval.regrade(tmp_path / "transcripts", write=False, results_dir=tmp_path / "results") == 1


def test_regrade_refuses_answers_to_another_task_version(tmp_path, capsys):
    run(tmp_path, FakeClient(scripted_replies()))
    path = next((tmp_path / "transcripts").rglob("trial_1.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["prompt"] = "an older version of this task"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert run_eval.regrade(tmp_path / "transcripts", write=False, results_dir=tmp_path / "results") == 1
    assert "NOT GRADED: 1 transcript(s)" in capsys.readouterr().out
    card = json.loads((tmp_path / "results" / "scorecard.json").read_text(encoding="utf-8"))
    assert card["n_transcripts"] == 7  # the stale one is not counted


def test_v1_pilot_transcripts_never_count_against_the_current_tasks():
    pilot = load_transcripts(run_eval.ROOT / "pilot_v1" / "transcripts")
    current, stale = split_stale(pilot, tasks_by_id())
    assert pilot and current == [] and len(stale) == len(pilot)


@pytest.mark.parametrize("entry, expected", [({"name": "m", "openrouter_id": None}, 0), ({"name": "m", "openrouter_id": "lab/m"}, 1)])
def test_models_without_verified_id_are_skipped(tmp_path, entry, expected):
    path = tmp_path / "models.yaml"
    path.write_text(json.dumps({"defaults": {"temperature": 0}, "models": [entry]}), encoding="utf-8")
    assert len(run_eval.load_model_specs(path, None)) == expected


@pytest.mark.parametrize(
    "models, message",
    [
        ([{"name": "m", "openrouter_id": None, "reasonning": {"effort": "high"}}], "unknown keys"),
        ([{"name": "m", "openrouter_id": None}, {"name": "m", "openrouter_id": None}], "duplicate model names"),
    ],
)
def test_models_yaml_mistakes_are_loud(tmp_path, models, message):
    path = tmp_path / "models.yaml"
    path.write_text(json.dumps({"models": models}), encoding="utf-8")
    with pytest.raises(SystemExit, match=message):
        run_eval.load_model_specs(path, None)


# --------------------------------------------------------------------------- client retries


def fake_response(finish_reason: str, content: str = "ok"):
    message = SimpleNamespace(content=content, model_extra={})
    choice = SimpleNamespace(finish_reason=finish_reason, message=message, model_extra={})
    return SimpleNamespace(choices=[choice], usage=None, model="m", model_extra={})


def client_with(responses, monkeypatch) -> OpenRouterClient:
    """OpenRouterClient whose API returns/raises the given items in order, with no sleeping."""
    async def create(**_kwargs):
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(client_module.asyncio, "sleep", no_sleep)
    client = OpenRouterClient("not-a-real-key", max_attempts=2)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client


def test_provider_error_mid_generation_is_an_api_error(monkeypatch):
    client = client_with([fake_response("error", "partial"), fake_response("error", "partial")], monkeypatch)
    result = asyncio.run(client.complete(GOOD, []))
    assert result.error and "mid-generation" in result.error and result.attempts == 2


def test_transient_failures_are_retried(monkeypatch):
    client = client_with([ValueError("garbled response"), fake_response("stop", "fine")], monkeypatch)
    result = asyncio.run(client.complete(GOOD, []))
    assert (result.error, result.text, result.attempts) == (None, "fine", 2)


def status_error(code: int, message: str, cls: type = openai.APIStatusError) -> openai.APIStatusError:
    """An APIStatusError (or subclass) without building an HTTP response object."""
    exc = cls.__new__(cls)
    Exception.__init__(exc, message)
    exc.status_code = code
    return exc


def test_out_of_credits_fails_fast_and_redacts_account_ids(monkeypatch):
    msg = "Error code: 402 - can only afford 420 tokens. Visit https://openrouter.ai/workspaces/default/keys/d6bd07e9abc"
    client = client_with([status_error(402, msg)], monkeypatch)
    result = asyncio.run(client.complete(GOOD, []))
    assert result.stop_run == STOP_NO_CREDITS and result.attempts == 1  # no pointless retries
    assert "d6bd07e9abc" not in result.error and "keys/<redacted>" in result.error


def test_free_daily_quota_stops_but_per_minute_limit_is_retried(monkeypatch):
    daily = status_error(429, "Rate limit exceeded: free-models-per-day. Add 10 credits to unlock more")
    result = asyncio.run(client_with([daily], monkeypatch).complete(GOOD, []))
    assert result.stop_run == STOP_FREE_DAILY and result.attempts == 1
    per_minute = status_error(429, "Rate limit exceeded: free-models-per-min.")
    result = asyncio.run(client_with([per_minute, fake_response("stop", "fine")], monkeypatch).complete(GOOD, []))
    assert (result.error, result.text, result.attempts) == (None, "fine", 2)


def test_max_requests_caps_a_run(tmp_path):
    client = FakeClient(scripted_replies())
    run(tmp_path, client, cost=CostTracker(max_requests=3))
    assert len(client.calls) == 3


def test_run_stops_after_out_of_credits(tmp_path):
    client = FakeClient({("bad-model", "task_01"): [CompletionResult(error="402", stop_run=STOP_NO_CREDITS)]})
    asyncio.run(run_trials(load_tasks(["task_01", "task_05"]), [BAD], 2, client, tmp_path / "t",
                           ResponseCache(tmp_path / "c"), CostTracker(), 1, log=lambda *_: None))
    assert len(client.calls) == 1  # the three remaining trials were never sent
    assert [t["grade"]["failure_code"] for t in load_transcripts(tmp_path / "t")] == ["API_ERROR"]


def test_refused_model_is_skipped_but_other_models_still_run(tmp_path, monkeypatch):
    refusal = status_error(403, "thinkingmachines/inkling:free is only available on agentic harnesses",
                           openai.PermissionDeniedError)
    result = asyncio.run(client_with([refusal], monkeypatch).complete(BAD, []))
    assert result.attempts == 1 and "HTTP 403" in result.skip_model and result.stop_run is None

    replies = scripted_replies()
    replies[("bad-model", "task_01")] = [result]
    client = FakeClient(replies)
    run(tmp_path, client)
    assert [c[0] for c in client.calls] == ["good-model"] * 4 + ["bad-model"]
    assert len(load_transcripts(tmp_path / "transcripts")) == 5  # skipped trials run next time


def test_model_is_skipped_after_failing_twice_in_a_row(tmp_path):
    ref1 = load_reference("task_01")["answer"]
    failed = CompletionResult(error="RateLimitError: 429 - Provider returned error", attempts=2)
    client = FakeClient({
        ("bad-model", "task_01"): [failed, ok(ref1), failed],  # the success in between resets the count
        ("bad-model", "task_05"): [failed],
    })
    asyncio.run(run_trials(load_tasks(["task_01", "task_05"]), [BAD], 3, client, tmp_path / "t",
                           ResponseCache(tmp_path / "c"), CostTracker(), 1, log=lambda *_: None))
    assert len(client.calls) == 4  # task_05 trials 2 and 3 were never sent
    assert len(load_transcripts(tmp_path / "t")) == 4


def test_live_run_requires_max_cost(tmp_path, capsys):
    path = tmp_path / "models.yaml"
    path.write_text(json.dumps({"models": [{"name": "m", "openrouter_id": "lab/m"}]}), encoding="utf-8")
    assert run_eval.main(["--models", str(path), "--trials", "1"]) == 1
    assert "cost money" in capsys.readouterr().out


def test_max_cost_zero_refuses_paid_models(tmp_path, capsys):
    path = tmp_path / "models.yaml"
    models = [{"name": "free", "openrouter_id": "lab/m:free"}, {"name": "paid", "openrouter_id": "lab/m"}]
    path.write_text(json.dumps({"models": models}), encoding="utf-8")
    assert run_eval.main(["--models", str(path), "--trials", "1", "--max-cost", "0"]) == 1
    assert "paid: paid" in capsys.readouterr().out


def test_free_models_estimate_zero():
    free = ModelSpec(name="f", openrouter_id="lab/m:free")
    (row,) = estimate([free], load_tasks(["task_01"]), 3, 1000, {})
    assert row["estimated_usd"] == 0.0 and "free" in row["basis"]


def test_committed_free_models_config_is_free_only():
    specs = run_eval.load_model_specs(run_eval.ROOT / "models.free.yaml", None)
    assert specs and all(s.openrouter_id.endswith(":free") for s in specs)


def test_dry_run_estimate_uses_observed_costs():
    tasks = load_tasks(["task_01", "task_05"])
    observed = {settings_key(GOOD.settings()): (0.01, 5)}
    good, bad = estimate([GOOD, BAD], tasks, 3, 1000, observed)
    assert good["estimated_usd"] == pytest.approx(0.06) and "avg" in good["basis"]
    assert bad["estimated_usd"] is None  # no history and no prices: honest "unknown"


def test_pass_at_k_is_a_fraction_and_api_errors_cost_nothing(tmp_path):
    run(tmp_path, FakeClient(scripted_replies()))
    card = summarize(load_transcripts(tmp_path / "transcripts"))
    good, bad = card["models"]["good-model"], card["models"]["bad-model"]
    assert isinstance(good["pass_at_k"], float) and "| 100% | 100% |" in render_markdown(card)
    assert bad["calls_with_unknown_cost"] == 0


def test_committed_models_yaml_has_no_guessed_ids():
    specs = run_eval.load_model_specs(run_eval.ROOT / "models.yaml", None)
    assert specs == [] or all("/" in s.openrouter_id for s in specs)
