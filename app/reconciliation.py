from dataclasses import dataclass
from datetime import date
from decimal import Decimal
try:
    from rapidfuzz.fuzz import ratio
except ImportError:  # permits dependency-light benchmark and deterministic fallback
    from difflib import SequenceMatcher
    def ratio(left: str, right: str) -> float:
        return SequenceMatcher(None, left, right).ratio() * 100


@dataclass(frozen=True)
class Candidate:
    id: str
    amount: Decimal
    transaction_date: date
    reference: str
    vendor: str = ""


@dataclass(frozen=True)
class Rule:
    amount_tolerance: Decimal = Decimal("0.00")
    date_tolerance_days: int = 3
    fuzzy_threshold: int = 85
    auto_approve_threshold: int = 95


@dataclass(frozen=True)
class MatchResult:
    left_id: str
    right_id: str
    confidence: int
    status: str
    amount_difference: Decimal
    reasoning: dict


class ReconciliationEngine:
    """Deterministic one-to-one matcher. Candidate tie breaks use stable transaction IDs."""

    def reconcile(self, left: list[Candidate], right: list[Candidate], rule: Rule) -> list[MatchResult]:
        available = {item.id: item for item in right}
        by_reference: dict[str, list[str]] = {}
        by_amount: dict[Decimal, list[str]] = {}
        for item in right:
            by_reference.setdefault(self._normalize(item.reference), []).append(item.id)
            by_amount.setdefault(item.amount, []).append(item.id)
        results: list[MatchResult] = []
        for source in sorted(left, key=lambda x: (x.transaction_date, x.id)):
            candidate_ids = by_reference.get(self._normalize(source.reference), [])
            if not candidate_ids:
                candidate_ids = by_amount.get(source.amount, [])
            # Fuzzy fallback is deliberately bounded to protect shared demo resources.
            pool = [available[item_id] for item_id in candidate_ids if item_id in available]
            if not pool and len(available) <= 2_000:
                pool = list(available.values())
            scored = [self._score(source, target, rule) for target in pool]
            eligible = [item for item in scored if item.confidence >= 50]
            if not eligible:
                continue
            best = sorted(eligible, key=lambda x: (-x.confidence, abs(x.amount_difference), x.right_id))[0]
            results.append(best)
            del available[best.right_id]
        return results

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())

    def _score(self, left: Candidate, right: Candidate, rule: Rule) -> MatchResult:
        amount_diff = (left.amount - right.amount).copy_abs()
        date_diff = abs((left.transaction_date - right.transaction_date).days)
        ref_score = int(ratio(left.reference.casefold().strip(), right.reference.casefold().strip())) if left.reference and right.reference else 0
        amount_ok = amount_diff <= rule.amount_tolerance
        date_ok = date_diff <= rule.date_tolerance_days
        exact_reference = bool(left.reference and left.reference.casefold().strip() == right.reference.casefold().strip())
        confidence = (45 if amount_ok else max(0, 45 - int(amount_diff))) + (25 if date_ok else max(0, 25 - date_diff * 5)) + int(ref_score * 0.30)
        confidence = min(100, confidence)
        if amount_ok and date_ok and (exact_reference or ref_score >= rule.fuzzy_threshold):
            status = "fully_matched" if confidence >= rule.auto_approve_threshold else "partially_matched"
        elif not amount_ok and date_ok and ref_score >= rule.fuzzy_threshold:
            status = "amount_mismatch"
        elif amount_ok and not date_ok and ref_score >= rule.fuzzy_threshold:
            status = "date_mismatch"
        else:
            status = "requires_manual_review"
        return MatchResult(left.id, right.id, confidence, status, amount_diff, {
            "amount": {"difference": str(amount_diff), "within_tolerance": amount_ok},
            "date": {"difference_days": date_diff, "within_tolerance": date_ok},
            "reference": {"similarity": ref_score, "threshold": rule.fuzzy_threshold},
        })

    def reconcile_grouped(self, left: Candidate, right: list[Candidate], rule: Rule) -> MatchResult | None:
        """One-to-many aggregate matching for same reference/vendor groups."""
        if not right:
            return None
        total = sum((x.amount for x in right), Decimal("0"))
        amount_diff = abs(left.amount - total)
        if amount_diff > rule.amount_tolerance:
            return None
        ids = sorted(x.id for x in right)
        return MatchResult(left.id, ",".join(ids), 95, "fully_matched", amount_diff, {
            "strategy": "one_to_many", "component_count": len(ids), "aggregate_amount": str(total)
        })
