from flask_pydantic_api.utils import unindent_text


def test_unindent_text():
    actual = unindent_text(
        "    Line 1, followed by an empty line which is tricky.\n"
        "\n"
        "    Then another line with right padding.     \n"
    )
    expected = (
        "Line 1, followed by an empty line which is tricky.\n"
        "\n"
        "Then another line with right padding."
    )

    assert actual == expected


def test_unindent_text__spaces():
    assert unindent_text("\n" "    \n" "\n") == ""
