"""Text normalisation shared by the code that reads customer messages."""

import re
import unicodedata

ZERO_WIDTH = re.compile("[​‌‍‎‏⁠﻿­]")
WHITESPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Fold look-alike characters, drop invisible ones, lower-case and collapse whitespace.

    Used before matching patterns, so that "Sm​ell  GAS" is read as "smell gas".
    """
    folded = unicodedata.normalize("NFKC", text)
    return WHITESPACE.sub(" ", ZERO_WIDTH.sub("", folded)).strip().lower()
