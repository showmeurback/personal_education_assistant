"""Символьная агрегация вердиктов оценщиков и разрешение рассогласований.

Каждый оценщик i даёт вердикт v_i и уверенность c_i. Оценка «за принятие»
p_i = c_i, если v_i = истина, иначе 1 − c_i. Итоговая оценка
P = Σ w_i·p_i / Σ w_i. Решение принимается по правилам:

  1) валидных оценок меньше k_min                 → ручная проверка;
  2) все «за» и P ≥ τ_accept                       → принять;
  3) все «против» и P ≤ τ_reject                   → отклонить;
  4) иначе (голоса разделились или низкая уверенность) → ручная проверка;
  5) если символьные правила сомневаются в теме отчёта (R6 или R7 = WARN),
     а оценщики решили «принять», — ручная проверка (противоречие компонентов);
  6) голоса 2:1, но большинство — оба «сильных» оценщика (AGG_STRONG_JUDGES), каждый
     с уверенностью ≥ AGG_STRONG_MIN_CONFIDENCE, а несогласен третий — решение по
     большинству (принять — только при отсутствии сомнения в теме). Правило проверяется
     перед правилом 4. Основание: на отложенном наборе сильные оценщики верны в 98 %
     проверок без общих ошибок, а несогласия почти всегда вызывал лояльный оценщик.
"""
from __future__ import annotations

from dataclasses import dataclass

from models.enums import VerificationDecision
from settings import verification_settings as cfg
from .judges import JudgeVerdict

DEFAULT_WEIGHTS = {"strict": 1.0, "objective": 1.0, "loyal": 1.0}


@dataclass
class AggregationResult:
    decision: VerificationDecision
    score: float | None
    votes_for: int
    votes_against: int
    valid: int
    rule: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value, "score": self.score, "votes_for": self.votes_for,
            "votes_against": self.votes_against, "valid": self.valid, "rule": self.rule,
            "reason": self.reason,
        }


def aggregate(verdicts: list[JudgeVerdict], *, topic_doubt: bool = False,
              weights: dict[str, float] | None = None,
              approve_threshold: float | None = None,
              reject_threshold: float | None = None,
              min_valid: int | None = None) -> AggregationResult:
    weights = weights or DEFAULT_WEIGHTS
    t_acc = cfg.approve_threshold if approve_threshold is None else approve_threshold
    t_rej = cfg.reject_threshold if reject_threshold is None else reject_threshold
    k_min = cfg.min_valid_judges if min_valid is None else min_valid

    valid = [v for v in verdicts if v.valid and v.p_accept is not None]
    votes_for = sum(1 for v in valid if v.verdict)
    votes_against = len(valid) - votes_for

    if len(valid) < k_min:
        return AggregationResult(VerificationDecision.MANUAL_REVIEW, None, votes_for, votes_against,
                                 len(valid), "A1",
                                 f"Получено {len(valid)} валидных оценок из {len(verdicts)} (нужно ≥ {k_min})")

    total_w = sum(weights.get(v.judge, 1.0) for v in valid)
    score = sum(weights.get(v.judge, 1.0) * v.p_accept for v in valid) / total_w
    score = round(score, 3)

    if votes_against == 0 and score >= t_acc:
        if topic_doubt:
            return AggregationResult(VerificationDecision.MANUAL_REVIEW, score, votes_for, votes_against,
                                     len(valid), "A5",
                                     "Оценщики приняли отчёт, но правило темы (R6 или R7) сомневается "
                                     "в соответствии работе — противоречие передано преподавателю")
        return AggregationResult(VerificationDecision.APPROVE, score, votes_for, votes_against,
                                 len(valid), "A2", f"Единогласно «за», P = {score:.2f} ≥ {t_acc}")
    if votes_for == 0 and score <= t_rej:
        return AggregationResult(VerificationDecision.REJECT, score, votes_for, votes_against,
                                 len(valid), "A3", f"Единогласно «против», P = {score:.2f} ≤ {t_rej}")
    strong_names = [j.strip() for j in cfg.strong_judges.split(",") if j.strip()]
    strong = [v for v in valid if v.judge in strong_names]
    if (votes_for and votes_against and len(strong) == len(strong_names) >= 2
            and len({v.verdict for v in strong}) == 1
            and all((v.confidence or 0) >= cfg.strong_min_confidence for v in strong)
            and sum(1 for v in valid if v.verdict == strong[0].verdict) == len(valid) - 1):
        names = ", ".join(v.title.lower() for v in strong)
        if strong[0].verdict:
            if topic_doubt:
                return AggregationResult(VerificationDecision.MANUAL_REVIEW, score, votes_for, votes_against,
                                         len(valid), "A5",
                                         "Сильные оценщики приняли отчёт, но правило темы сомневается — "
                                         "противоречие передано преподавателю")
            return AggregationResult(VerificationDecision.APPROVE, score, votes_for, votes_against, len(valid),
                                     "A6", f"Голоса {votes_for}:{votes_against}; «за» уверенно голосуют "
                                           f"сильные оценщики ({names}), P = {score:.2f}")
        return AggregationResult(VerificationDecision.REJECT, score, votes_for, votes_against, len(valid),
                                 "A6", f"Голоса {votes_for}:{votes_against}; «против» уверенно голосуют "
                                       f"сильные оценщики ({names}), P = {score:.2f}")
    if votes_for and votes_against:
        reason = f"Голоса разделились {votes_for}:{votes_against}, P = {score:.2f}"
    else:
        reason = f"Единогласное решение с недостаточной уверенностью, P = {score:.2f}"
    return AggregationResult(VerificationDecision.MANUAL_REVIEW, score, votes_for, votes_against,
                             len(valid), "A4", reason)


def majority_vote(verdicts: list[JudgeVerdict]) -> VerificationDecision:
    """Решение «только нейросетевого» варианта (для сравнительного эксперимента)."""
    valid = [v for v in verdicts if v.valid and v.verdict is not None]
    votes_for = sum(1 for v in valid if v.verdict)
    return VerificationDecision.APPROVE if votes_for * 2 > len(valid) and valid else VerificationDecision.REJECT
