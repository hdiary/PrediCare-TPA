from rag.ingestion.chunker import Page, _tokens, chunk_pages


def test_chunk_pages_prefixes_contract_and_preserves_article_and_page():
    chunks = chunk_pages(
        [Page(3, "Article 4 - Optique\nPlafond annuel : 300 euros.")],
        "CTR-000001")

    assert len(chunks) == 1
    assert chunks[0].content.startswith(
        "[Contrat CTR-000001 > Article 4 - Optique]")
    assert chunks[0].article == "Article 4 - Optique"
    assert chunks[0].page_start == chunks[0].page_end == 3


def test_chunk_pages_splits_long_paragraph_with_overlap():
    text = " ".join(f"mot{i}" for i in range(40))
    chunks = chunk_pages(
        [Page(1, text)], "CTR-000001", max_tokens=12, overlap_tokens=3)

    assert len(chunks) > 1
    first_body = chunks[0].content.split("] ", 1)[1]
    second_body = chunks[1].content.split("] ", 1)[1]
    assert _tokens(first_body)[-3:] == _tokens(second_body)[:3]
    assert all(len(_tokens(chunk.content.split("] ", 1)[1])) <= 12
               for chunk in chunks)


def test_chunk_pages_ignores_empty_pages():
    assert chunk_pages([Page(1, "  \n "), Page(2, "Clause active")],
                       "CTR-000001")


def test_chunk_pages_supports_formula_and_global_context():
    formula_chunks = chunk_pages(
        [Page(1, "Garanties de la formule.")], None, formula="CONFORT")
    global_chunks = chunk_pages(
        [Page(1, "Réseau de soins.")], None, global_scope=True)

    assert formula_chunks[0].content.startswith("[Formule CONFORT]")
    assert global_chunks[0].content.startswith(
        "[Document général PrediCare]")
