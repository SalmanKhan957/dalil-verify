from pipelines.evaluation.hadith.run_hadith_topical_eval import load_judgments


def test_seed_judgments_load() -> None:
    judgments = load_judgments('pipelines/evaluation/hadith/judged_queries/seed_queries.json')
    assert any(item.query_text == 'give hadith about rizq' for item in judgments)
    assert any('anger' in item.expected_topics for item in judgments)
