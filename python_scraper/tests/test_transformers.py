import pytest
from typing import Optional
from src.transformers import parse_course_name


@pytest.mark.parametrize(
    "input_str, expected_nome, expected_classe",
    [
        ("Informatica L-31", "Informatica", "L-31"),
        ("Matematica LM-40", "Matematica", "LM-40"),
        ("Informatica   L-31", "Informatica", "L-31"),
        ("Storia Romana", "Storia Romana", ""),
        ("", "", ""),
        (None, "", ""),
    ],
)
def test_parse_course_name(
    input_str: Optional[str],
    expected_nome: str,
    expected_classe: str,
) -> None:

    # act
    nome, classe = parse_course_name(input_str)

    # assert
    assert nome == expected_nome
    assert classe == expected_classe
    assert nome == expected_nome
    assert classe == expected_classe
