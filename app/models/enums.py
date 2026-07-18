from enum import Enum


class AccountType(str, Enum):
    checking = "checking"
    savings = "savings"
    cash = "cash"
    credit_card = "credit_card"
    other = "other"


class TransactionType(str, Enum):
    expense = "expense"
    income = "income"
    transfer = "transfer"


class ImportSource(str, Enum):
    manual = "manual"
    csv = "csv"
    excel = "excel"
    pdf = "pdf"


class MatchField(str, Enum):
    description = "description"
    amount = "amount"
    account = "account"


class MatchType(str, Enum):
    contains = "contains"
    exact = "exact"
    starts_with = "starts_with"
    regex = "regex"


class ImportBatchStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    undone = "undone"


class BudgetPeriod(str, Enum):
    monthly = "monthly"  # limite por mes natural, repetido cada mes del rango
    range = "range"      # limite total para el rango de fechas completo


class SubscriptionFrequency(str, Enum):
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"
    other = "other"
