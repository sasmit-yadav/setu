from __future__ import annotations

from services.ml.flores import SOURCE_FLORES, flores_target, is_english


def test_kerala_and_maharashtra_map_to_indictrans2_tags():
    assert flores_target("ml") == "mal_Mlym"
    assert flores_target("MR") == "mar_Deva"
    assert flores_target("hi") == "hin_Deva"


def test_english_is_the_en_indic_source_side():
    assert is_english("en")
    assert flores_target("en") == SOURCE_FLORES
    assert flores_target("eng_Latn") == SOURCE_FLORES


def test_unknown_iso_is_refused_not_guessed():
    assert flores_target("xx") is None
    assert flores_target("") is None
