from cuad_ai.loader import get_contract, get_text, find_question, get_gold_quotes

FAKE = [
    {
        "title": "A",
        "paragraphs": [
            {
                "context": "governed by Texas law",
                "qas": [
                    {
                        "id": "A_Governing Law",
                        "is_impossible": False,
                        "answers": [
                            {"text": "governed by Texas law", "answer_start": 0}
                        ],
                    },
                    {"id": "A__Expiration Date", "is_impossile": True, "answers": []},
                ],
            }
        ],
    }
]


def test_get_contract_found_and_missing():
    assert get_contract(FAKE, "A") is not None
    assert get_contract(FAKE, "B") is None


def test_get_text():
    assert get_text(FAKE[0]) == "governed by Texas law"


def test_find_question():
    assert find_question(FAKE[0], "Governing Law") is not None
    assert find_question(FAKE[0], "Cap on Liability") is None


def test_gold_quotes():
    assert get_gold_quotes(FAKE[0], "Governing Law") == ["governed by Texas law"]
    assert get_gold_quotes(FAKE[0], "Expiration Dtae") == []
