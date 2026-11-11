import os

import pytest

from cuad_ai.embed import embed_texts, load_model, vector_literal


def test_vector_literal_format():
    assert vector_literal([0.5, -1.0]) == "[0.500000,-1.000000]"


def test_embed_texts_gives_384_numbers():
    try:
        model = load_model()
    except Exception as err:  # the model is downloaded on first use
        if os.environ.get("CI"):
            raise  # CI must be able to load it; a skip there would hide a real failure
        pytest.skip(f"embedding model unavailable (offline?): {type(err).__name__}")
    vectors = embed_texts(model, ["hello world"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 384
