from dataclasses import dataclass
from typing import List, Optional

from common.string import JournaledString
from common.types import SerializableEntity, Term
from entities.sentences.types import Sentence


@dataclass(frozen=True)
class EmbellishedSentence(Sentence):
    """
    A sentence embellished with additional text to make it easier to detect definitions. For
    example, one embellishment is surrounding all top-level symbols in a clear delimiter.
    Should share the same 'tex_path' and 'id_' as the sentence it was derived from.
    All embellishments are accompanied with a JournaledString that can be used to recover
    positions of spans in the embellished sentence back to the original TeX.
    """

    legacy_definition_input: str
    " All equations replaced with 'SYMBOL'. "
    legacy_definition_input_journal: JournaledString

    with_formulas_marked: str
    " All equations replaced with '(((FORMULA:<TeX>)))'. "
    with_formulas_marked_journal: JournaledString

    with_symbols_marked: str
    " All top-level symbols surrounded with SYMBOL_START and SYMBOL_END tokens. "
    with_symbols_marked_journal: JournaledString


@dataclass(frozen=True)
class Token:
    """
    A token from a sentence extracted from TeX. Note that this token may be taken from a
    transformed version of the sentence, i.e., one that has been modified to be easier to process.
    For instance, the token may have been produced by splitting a sentence stored as the
    'with_symbols_marked' property of the EmbellishedSentence class.
    """

    text: str
    " The token. "

    text_for_annotation: Optional[str]
    """
    When assembling a text to be annotated, this value should be written to the text to be
    annotated, instead of the 'text' property. Set this to 'None' if the token should not
    be written to the text to be annotated at all.
    """

    tex: str
    " The original TeX for the token (before any transformations). "

    tex_start: int
    tex_end: int
    """
    Character offsets that bounding where this token appeared (or the text that was transformed into
    this token) in the original TeX.
    """

    sentence_id: str
    " ID of the sentence this token belongs to. "

    sentence_transformations: Optional[str]
    """
    Optional tag describing types of transformations that had been applied to the sentence before
    tokens were extracted from it.
    """


@dataclass(frozen=True)
class AnnotationToken(Token):
    """
    A token output to a text meant to be annotated. Includes offsets of where the token appears
    both in the original TeX that it was found in, and the synthesized text to be annotated.
    """

    start_in_text: Optional[int]
    end_in_text: Optional[int]
    """
    Offsets indicating the character positions where the token appears in the output text. Set
    to 'None' if the token wasn't written to the text to be annotated.
    """

    start_in_sentence: Optional[int]
    end_in_sentence: Optional[int]
    """
    Offsets indicating the character positions where the token appears in the sentence it belongs
    to in the output text. This is useful for finding the token in the output text if the text
    is written such that each sentence is listed on its own line. Set to 'None' if the token wasn't
    written to the text to be annotated.
    """


@dataclass(frozen=True)
class Definition(SerializableEntity):
    """
    A passage that defines a term. In many cases, this will only include the definiens---the
    part of a passage that defines the term, and not the defined term itself.
    IDs for definitions should include the 'tex_path', because terms will need to have
    unique references to definitions by their IDs, and terms will not always appear in the
    same TeX file as the definition.
    """

    text: str
    sentence_id: str

    definiendum: str
    " The name of the term that this definition defines. "

    type_: Optional[str]
    " Type of definition (e.g., nickname, expansion, definition). "

    intent: bool
    " Whether this definition is high enough quality to extract. "

    confidence: Optional[float]


@dataclass(frozen=True)
class TermReference(Term):
    " A reference to a defined term in the text. "

    definition_ids: List[str]
    " A list of IDs of definitions found in the text that define this term. "

    definition_texs: List[str]
    " The original TeX for each definition in 'definitions'. "

    position_ratios: List[float]
    " A list of the term' position ratios in the paper. "

    section_names: List[str]
    " A list of section names of the term. "


@dataclass(frozen=True)
class Definiendum(TermReference):
    " A term that appears in a definition. "

    sentence_id: str

    definition_id: str
    " The ID for the definiens that defines this term. "

    confidence: Optional[float]
    " The confidence score of the model's prediction. "

    position_ratio: float
    " The relative ratio of the term in the paper (character ratio of the start of term to the total number of characters). Range is 0 to 1"

    section_name: Optional[str]
    " The name of section that defines this term. "
