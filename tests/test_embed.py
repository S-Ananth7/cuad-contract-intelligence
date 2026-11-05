from cuad_ai.embed import embed_texts, load_model, vector_literal


def test_vector_literal_format():
    assert vector_literal([0.5, -1.0]) == "[0.500000,-1.000000]"


def test_embed_texts_gives_384_numbers():
    vectors = embed_texts(load_model(), ["hello world"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 384
