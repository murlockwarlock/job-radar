import html
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(re.sub(r"<[^>]+>", " ", value)).lower().replace("ё", "е")
    value = re.sub(r"[^\w\s+#.-]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _contains(text: str, keyword: str) -> bool:
    needle = normalize_text(keyword)
    if not needle:
        return False
    if " " in needle:
        return needle in text
    return re.search(rf"(?<![\w]){re.escape(needle)}(?![\w])", text, re.UNICODE) is not None


@dataclass(slots=True)
class FilterResult:
    matched: bool
    match_reasons: list[str] = field(default_factory=list)
    reject_reasons: list[str] = field(default_factory=list)


class FilterEngine:
    def evaluate(self, vacancy: Any, profile: Any) -> FilterResult:
        title = normalize_text(getattr(vacancy, "title", None))
        description = normalize_text(getattr(vacancy, "description", None))
        skills = normalize_text(" ".join(getattr(vacancy, "key_skills", []) or []))
        employer = normalize_text(getattr(vacancy, "employer_name", None))
        searchable = " ".join(part for part in (title, description, skills, employer) if part)
        reasons: list[str] = []
        rejects: list[str] = []

        include = [item for item in (profile.include_keywords or []) if item.strip()]
        include_hits = [item for item in include if _contains(searchable, item)]
        if include and len(include_hits) < max(1, int(profile.include_min_matches or 1)):
            rejects.append(f"include_keywords: {len(include_hits)}/{len(include)}")
        else:
            reasons.extend(f"keyword: {item}" for item in include_hits)

        required_missing = [
            item for item in profile.required_keywords or [] if not _contains(searchable, item)
        ]
        if required_missing:
            rejects.append("required_keywords: " + ", ".join(required_missing))
        else:
            reasons.extend(f"required: {item}" for item in profile.required_keywords or [])

        excluded = [item for item in profile.exclude_keywords or [] if _contains(searchable, item)]
        if excluded:
            rejects.append("exclude_keywords: " + ", ".join(excluded))

        excluded_companies = [
            item for item in profile.excluded_companies or [] if _contains(employer, item)
        ]
        if excluded_companies:
            rejects.append("excluded_companies: " + ", ".join(excluded_companies))

        if profile.area_ids and str(getattr(vacancy, "area_id", "")) not in {
            str(x) for x in profile.area_ids
        }:
            rejects.append("area")
        if profile.schedules and str(getattr(vacancy, "schedule_id", "")) not in {
            str(x) for x in profile.schedules
        }:
            rejects.append("schedule")
        if profile.employment_types and str(getattr(vacancy, "employment_id", "")) not in {
            str(x) for x in profile.employment_types
        }:
            rejects.append("employment")
        if profile.experience_levels and str(getattr(vacancy, "experience_id", "")) not in {
            str(x) for x in profile.experience_levels
        }:
            rejects.append("experience")

        salary_from = getattr(vacancy, "salary_from", None)
        salary_to = getattr(vacancy, "salary_to", None)
        if profile.only_with_salary and salary_from is None and salary_to is None:
            rejects.append("salary_missing")
        if profile.salary_min is not None:
            if profile.currency and getattr(vacancy, "salary_currency", None) != profile.currency:
                rejects.append("salary_currency")
            else:
                upper = salary_to or salary_from
                if upper is None or Decimal(str(upper)) < Decimal(str(profile.salary_min)):
                    rejects.append(f"salary_below:{profile.salary_min}")
                else:
                    reasons.append(f"salary>={profile.salary_min}")

        return FilterResult(not rejects, reasons, rejects)
