"""scripts/explain_failures.py: finds exactly the planted fault in a mutated reference DFA."""
from automata.dfa import DFA, equivalent
from explain_failures import access_words, explain, faults, first_fault_on
from graders.grader import reference_dfa
from harness.prompts import tasks_by_id

TASK = tasks_by_id()["task_01"]


def mutated(dfa: DFA, **update) -> DFA:
    return dfa.model_copy(update=update, deep=True)


def test_reference_has_no_faults():
    ref = reference_dfa(TASK)
    assert faults(ref, ref) == (set(), set())


def test_flipped_flag_is_the_only_fault():
    ref = reference_dfa(TASK)
    q = next(s for s in ref.states if s not in ref.accepting)
    model = mutated(ref, accepting=ref.accepting + [q])
    assert faults(model, ref) == (set(), {q})


def test_redirected_transition_is_found_on_the_counterexample():
    ref = reference_dfa(TASK)
    access = access_words(ref)
    tree = {(access_q[:-1], access_q[-1]) for access_q in access.values() if access_q}  # BFS tree edges as words
    # a transition outside the BFS tree, so every state keeps its access word after the mutation
    q, x = next((q, x) for q in ref.states for x in ref.alphabet if (access[q], x) not in tree)
    wrong = next(s for s in ref.states if s != ref.transitions[q][x])
    transitions = {s: dict(row) for s, row in ref.transitions.items()}
    transitions[q][x] = wrong
    model = mutated(ref, transitions=transitions)
    same, cex = equivalent(model, ref)
    assert not same
    bad_moves, bad_flags = faults(model, ref)
    assert (bad_moves, bad_flags) == ({(q, x)}, set())
    assert first_fault_on(model, cex, bad_moves, bad_flags)[1:] == (x, q)
    transcript = {"parsed_answer": model.model_dump(), "grade": {"counterexample": cex}}
    assert f"{q!r} --{x}--> {wrong!r}" in explain(transcript, TASK)
