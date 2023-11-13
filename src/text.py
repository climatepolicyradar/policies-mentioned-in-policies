import re


def normalise_text(input_string: str) -> str:
    # remove newlines and multiple spaces
    clean_string = re.sub(r"\s+", " ", input_string).strip()
    # remove all non-ascii characters
    clean_string = re.sub(r"[^\x00-\x7F]+", "", clean_string)
    # lowercase
    clean_string = clean_string.lower()
    # remove punctuation
    clean_string = re.sub(r"[^\w\s]", "", clean_string)
    return clean_string
