from decimal import Decimal
from types import SimpleNamespace

from app.filtering.engine import FilterEngine, normalize_text


def profile(**overrides):
    values = dict(
        include_keywords=["горный инженер", "Micromine"],
        include_min_matches=1,
        required_keywords=[],
        exclude_keywords=["строительство"],
        excluded_companies=[],
        area_ids=[],
        schedules=[],
        employment_types=[],
        experience_levels=[],
        salary_min=None,
        currency=None,
        only_with_salary=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def vacancy(**overrides):
    values = dict(
        title="ГОРНЫЙ ИНЖЕНЕР",
        description="Планирование работ",
        key_skills=["Micromine"],
        employer_name="Рудник",
        area_id=None,
        schedule_id=None,
        employment_id=None,
        experience_id=None,
        salary_from=Decimal("500000"),
        salary_to=Decimal("650000"),
        salary_currency="KZT",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_normalize_text_removes_html_and_yo() -> None:
    assert normalize_text("<b>Ёлка</b>   Вакансия!") == "елка вакансия"


def test_include_and_required_keywords_match() -> None:
    result = FilterEngine().evaluate(vacancy(), profile(required_keywords=["планирование"]))
    assert result.matched is True
    assert any("горный инженер" in reason for reason in result.match_reasons)


def test_excluded_keyword_rejects() -> None:
    result = FilterEngine().evaluate(vacancy(description="Гражданское строительство"), profile())
    assert result.matched is False
    assert any("exclude_keywords" in reason for reason in result.reject_reasons)


def test_salary_filter_rejects_below_threshold() -> None:
    result = FilterEngine().evaluate(
        vacancy(salary_to=Decimal("100000")), profile(salary_min=Decimal("200000"), currency="KZT")
    )
    assert result.matched is False
    assert any("salary_below" in reason for reason in result.reject_reasons)
