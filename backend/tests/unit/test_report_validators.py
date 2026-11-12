"""Валидаторы протокола."""

from app.reporting.validators import has_forbidden_language, quote_is_grounded


def test_quote_grounded():
    assert quote_is_grounded("около  двух лет", "Работаю с PostgreSQL около двух лет")


def test_forbidden_language():
    assert has_forbidden_language("Кандидат подходит, 8/10")
    assert not has_forbidden_language("Упомянут опыт с PostgreSQL")
