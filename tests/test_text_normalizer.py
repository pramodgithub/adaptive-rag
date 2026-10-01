from services.ingestion.normalization.text_normalizer import normalize_text


def test_removes_bidi_formatting():
    text = "\u202dSOC 2 TYPE 2 REPORT\u202c"

    assert normalize_text(text) == "SOC 2 TYPE 2 REPORT"


def test_removes_all_supported_bidi_controls():
    controls = (
        "\u202a"
        "\u202b"
        "\u202c"
        "\u202d"
        "\u202e"
        "\u2066"
        "\u2067"
        "\u2068"
        "\u2069"
    )

    text = f"{controls}SOC 2{controls}"

    assert normalize_text(text) == "SOC 2"


def test_preserves_normal_text():
    text = "Access control policy requires MFA."

    assert normalize_text(text) == text


def test_preserves_legal_text():
    text = (
        "Article 32: The controller and the processor shall implement "
        "appropriate technical and organisational measures."
    )

    assert normalize_text(text) == text
