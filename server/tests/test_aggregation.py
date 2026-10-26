from agents.verification.aggregation import aggregate, majority_vote
from agents.verification.judges import JudgeVerdict
from models.enums import VerificationDecision as D


def v(judge, verdict, conf=0.9, valid=True):
    return JudgeVerdict(judge=judge, title=judge, valid=valid, verdict=verdict if valid else None,
                        confidence=conf if valid else None)


def test_unanimous_confident_approve():
    r = aggregate([v("strict", True), v("objective", True), v("loyal", True)])
    assert r.decision is D.APPROVE and r.rule == "A2" and r.score == 0.9


def test_unanimous_confident_reject():
    r = aggregate([v("strict", False), v("objective", False), v("loyal", False)])
    assert r.decision is D.REJECT and r.rule == "A3"


def test_split_vote_goes_to_manual_review():
    r = aggregate([v("strict", False), v("objective", True), v("loyal", True)])
    assert r.decision is D.MANUAL_REVIEW and r.rule == "A4" and "2:1" in r.reason


def test_unanimous_but_unsure_goes_to_manual_review():
    r = aggregate([v("strict", True, 0.55), v("objective", True, 0.6), v("loyal", True, 0.6)])
    assert r.decision is D.MANUAL_REVIEW


def test_not_enough_valid_judges():
    r = aggregate([v("strict", True), v("objective", None, valid=False), v("loyal", None, valid=False)])
    assert r.decision is D.MANUAL_REVIEW and r.rule == "A1"


def test_contradiction_between_rules_and_judges():
    r = aggregate([v("strict", True), v("objective", True), v("loyal", True)], topic_doubt=True)
    assert r.decision is D.MANUAL_REVIEW and r.rule == "A5"


def test_two_valid_judges_are_enough():
    r = aggregate([v("strict", True), v("objective", True), v("loyal", None, valid=False)])
    assert r.decision is D.APPROVE and r.valid == 2


def test_majority_vote_for_neural_only_variant():
    assert majority_vote([v("strict", False), v("objective", True), v("loyal", True)]) is D.APPROVE
    assert majority_vote([v("strict", False), v("objective", False), v("loyal", True)]) is D.REJECT
