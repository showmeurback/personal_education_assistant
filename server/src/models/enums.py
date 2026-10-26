from enum import Enum


class ReportStatus(Enum):
    CHECKING = "checking"            # принят к проверке, гибридная проверка выполняется
    PENDING = "pending"              # прошёл автоматическую проверку, ждёт преподавателя
    APPROVED = "approved"            # принят преподавателем
    NOT_APPROVED = "not-approved"    # отклонён преподавателем
    AI_REJECTED = "ai-rejected"      # отклонён гибридной системой (можно пересдать)
    MANUAL_REVIEW = "manual-review"  # компоненты не согласны — нужна ручная проверка


class VerificationDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MANUAL_REVIEW = "manual_review"


# совместимость со старым кодом
VerificationStatus = VerificationDecision
