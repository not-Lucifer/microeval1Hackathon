"""End-to-end harness tests with a fake client: no network, no API key."""
import asyncio
import json
from types import SimpleNamespace

import pytest

import run_eval
from graders.grader import load_reference
from harness import client as client_module
from harness.cache import ResponseCache
from harness.client import CompletionResult, ModelSpec, OpenRouterClient
from harness.cost import CostTracker
from harness.metrics import load_transcripts, render_markdown, summarize
from harness.parsing import extract_final_json
from harness.prompts import load_tasks
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
    assert "good-model" in render_markdown(card)
    # every transcript stores what a judge needs
    t = transcripts[0]
    for key in ("prompt", "system_prompt", "raw_output", "settings", "date", "usage", "grade", "finish_reason"):
        assert key in t


def test_cache_avoids_repeat_calls_but_not_api_errors(tmp_path):
    client = FakeClient(scripted_replies())
    run(tmp_path, client)
    assert len(client.calls) == 8
    retry = FakeClient({("bad-model", "task_05"): [ok({"witness": "bababbabaa"})]})
    run(tmp_path, retry)
    assert [c[0] for c in retry.calls] == ["bad-model"]  # only the API_ERROR trial was retried


def test_max_cost_stops_new_calls(tmp_path):
    client = FakeClient(scripted_replies())
    run(tmp_path, client, cost=CostTracker(max_usd=0.0))
    assert client.calls == []


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


def test_committed_models_yaml_has_no_guessed_ids():
    specs = run_eval.load_model_specs(run_eval.ROOT / "models.yaml", None)
    assert specs == [] or all("/" in s.openrouter_id for s in specs)
