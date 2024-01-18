import re


def normalise_text(input_string: str) -> str:
    # remove newlines and multiple spaces
    clean_string = re.sub(r"\s+", " ", input_string).strip()
    # remove all non-ascii characters
    clean_string = re.sub(r"[^\x00-\x7F]+", "", clean_string)
    # lowercase
    #clean_string = clean_string.lower()
    # remove punctuation
    clean_string = re.sub(r"[^\w\s]", "", clean_string)
    return clean_string

def check_for_country_and_title(text_blocks, title, geography):
    for text in text_blocks:
        if title in text and geography in text:
            return True
    return False

def check_document_mention(document_i, document_j, title_j, full_text_i):
    if document_i.document_metadata.geography_iso == document_j.document_metadata.geography_iso:
        exists = title_j.lower() in full_text_i.lower()
    else:
        if document_j.document_metadata.geography != "nan":
            text_blocks = [passage for block in document_i.text_blocks for passage in block.text]
            exists = check_for_country_and_title(text_blocks, title_j, document_j.document_metadata.geography)
        else:
            exists = title_j in full_text_i

    if exists and (document_j.document_metadata.publication_ts < document_i.document_metadata.publication_ts):
        return True
    else:
        return False