import pytest
from live_fakes import CONTRACT, DELAWARE, FakeEmbedder, FakeModel, T, load_bank_rows, submit

from cuad_ai.ingest import chunk_spans
from cuad_ai.live import store
from cuad_ai.live.locate import locate
from cuad_ai.live.process import LockedEmbedder, load_bank, process, rank_clauses
from cuad_ai.live.retrieve import retrieve_spans
from cuad_ai.search import search_hybrid

JUDGE_YES = '{"is_this_clause": true, "looks_like": "none"}'
JUDGE_NO = '{"is_this_clause": false, "looks_like": "Parties"}'


@pytest.fixture
def env(live_db):
    embedder = LockedEmbedder(FakeEmbedder())
    with live_db() as conn:
        load_bank_rows(conn, embedder)
        bank = load_bank(conn)
    return live_db, embedder, bank


def run(env, model, filename="upload.txt", text=CONTRACT):
    connect, embedder, bank = env
    with connect() as conn:
        sid = submit(conn, filename, text)
        sub = store.claim(conn)
        sub["excluded_company"] = store.get_submission(conn, T, sid)["excluded_company"]
    ok = process(connect, sub, model, embedder, bank, workers=2)
    with connect() as conn:
        answers = {a["clause"]: a for a in store.get_answers(conn, T, sid)}
        return ok, store.get_submission(conn, T, sid), answers


def test_a_whole_upload_runs_and_every_question_gets_an_answer(env):
    ok, sub, answers = run(env, FakeModel({"Governing Law": DELAWARE}))
    assert ok and sub["status"] == "done" and sub["done_questions"] == sub["total_questions"] == 4
    assert set(answers) == {"Governing Law", "Anti-Assignment", "Document Name", "Parties"}
    assert answers["Parties"]["decision"] == "not_found"
    assert sub["tokens_in"] > 0


def test_a_sure_answer_is_accepted_and_its_quote_is_located_in_the_real_text(env):
    model = FakeModel({"Governing Law": DELAWARE})
    _, _, answers = run(env, model)
    law = answers["Governing Law"]
    assert (law["decision"], law["reason"]) == ("accept", "accept")
    start, end = law["spans"][0]
    assert " ".join(CONTRACT[start:end].split()) == DELAWARE
    assert (start, end) == locate(CONTRACT, DELAWARE)


def test_an_unsure_answer_is_judged_twice_and_both_yes_accepts(env):
    model = FakeModel({"Parties": DELAWARE}, judge1=JUDGE_YES)  # Parties has no bank examples, so it is never 'sure'
    _, _, answers = run(env, model)
    assert (answers["Parties"]["decision"], answers["Parties"]["reason"]) == ("accept", "both_judges_yes")
    assert (answers["Parties"]["verdict"], answers["Parties"]["verdict2"]) == (True, True)


def test_judges_that_disagree_send_the_answer_to_a_person(env):
    model = FakeModel({"Parties": DELAWARE}, judge1=JUDGE_YES, judge2=JUDGE_NO)
    _, _, answers = run(env, model)
    assert (answers["Parties"]["decision"], answers["Parties"]["reason"]) == ("queue", "judges_disagree")
    assert answers["Parties"]["looks_like"] == ["Parties"]


def test_a_judge_reply_that_is_not_a_real_boolean_is_never_a_yes(env):
    model = FakeModel({"Parties": DELAWARE}, judge1='{"is_this_clause": "true", "looks_like": "none"}')
    _, _, answers = run(env, model)
    assert (answers["Parties"]["decision"], answers["Parties"]["reason"]) == ("queue", "judge_missing")


def test_both_judges_no_rejects(env):
    _, _, answers = run(env, FakeModel({"Parties": DELAWARE}, judge1=JUDGE_NO))
    assert (answers["Parties"]["decision"], answers["Parties"]["reason"]) == ("reject", "both_judges_no")


def test_an_invented_quote_is_queued_and_has_no_highlight(env):
    _, _, answers = run(env, FakeModel({"Governing Law": "This Agreement is governed by the laws of Texas."}))
    law = answers["Governing Law"]
    assert (law["decision"], law["reason"], law["spans"], law["retried"]) == ("queue", "quote_unverified", [], True)


def test_a_model_that_is_down_fails_the_upload_quickly_with_a_clear_reason(env, monkeypatch):
    monkeypatch.setattr("cuad_ai.live.process.EARLY_STOP_ERRORS", 2)
    ok, sub, _ = run(env, FakeModel(fail=True))
    assert not ok and sub["status"] == "failed" and "could not be reached" in sub["error"]


def test_the_token_cap_stops_a_runaway_upload(env, monkeypatch):
    monkeypatch.setenv("LIVE_TOKEN_CAP", "50")
    ok, sub, _ = run(env, FakeModel({"Governing Law": DELAWARE}))
    assert not ok and "token limit" in sub["error"]


def test_a_rerun_starts_clean(env):
    connect, embedder, bank = env
    run(env, FakeModel({"Governing Law": DELAWARE}))
    with connect() as conn:
        sub = {**dict(zip(("id", "filename", "text", "excluded_company"),
                          conn.execute("SELECT id, filename, text, excluded_company FROM live_submissions").fetchone()))}
    process(connect, sub, FakeModel(), embedder, bank, workers=2)
    with connect() as conn:
        assert {a["decision"] for a in store.get_answers(conn, T, sub["id"])} == {"not_found"}
        assert conn.execute("SELECT count(*) FROM live_chunks").fetchone()[0] == len(chunk_spans(CONTRACT))


def test_an_upload_that_is_a_known_cuad_contract_never_sees_that_companys_examples(env):
    connect, embedder, _ = env
    quote = "This Agreement shall be governed by and construed in accordance with the laws of the State of New York."
    with connect() as conn:
        assert "Governing Law" in rank_clauses(conn, embedder, [quote], "")
        assert "Governing Law" not in rank_clauses(conn, embedder, [quote], "Acme")  # its only example is Acme's
    with connect() as conn:
        bank = load_bank(conn, "Acme")
    ok, sub, answers = run((connect, embedder, bank), FakeModel({"Governing Law": DELAWARE}), filename="Acme_2020_x.txt")
    assert sub["excluded_company"] == "Acme"
    assert answers["Governing Law"]["rank_asked"] is None  # no example left to compare with
    assert answers["Governing Law"]["decision"] != "accept"


def test_live_retrieval_picks_the_same_excerpts_as_the_saved_runs_search(env):
    """The upload's chunks are copied into the CUAD tables as a bank contract of another company: both searches
    must choose the same spans in the same order."""
    connect, embedder, bank = env
    with connect() as conn:
        sid = submit(conn, "upload.txt", CONTRACT)
        spans = chunk_spans(CONTRACT)
        vectors = [v.tolist() for v in embedder.embed([CONTRACT[s:e] for s, e in spans])]
        store.save_chunks(conn, sid, [(s, e, CONTRACT[s:e], v) for (s, e), v in zip(spans, vectors)])
        cid = conn.execute("INSERT INTO contracts (title, company, n_chars) VALUES ('Gamma_x.txt', 'Gamma', %s) "
                           "RETURNING id", (len(CONTRACT),)).fetchone()[0]
        from cuad_ai.embed import vector_literal
        for (s, e), v in zip(spans, vectors):
            conn.execute("INSERT INTO chunks (contract_id, start_char, end_char, text, embedding) "
                         "VALUES (%s, %s, %s, %s, %s::vector)", (cid, s, e, CONTRACT[s:e], vector_literal(v)))
        conn.commit()
        for clause in ("Governing Law", "Anti-Assignment"):
            stems = ["govern", "law", "assign", "consent"]
            saved = [(s, e) for s, e, _ in search_hybrid(conn, cid, bank.clause_ids[clause], stems, k=10)]
            live = retrieve_spans(conn, sid, clause, bank.clause_ids[clause], stems, "")
            assert live == saved and live
