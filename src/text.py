import re
import pycountry
import pandas as pd
from typing import Optional

csv_url = "https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes/raw/master/all/all.csv"
iso_df = pd.read_csv(csv_url)
iso_data = dict(zip(iso_df['alpha-3'], iso_df['name']))

def normalise_text(input_string: str) -> str:
    # remove newlines and multiple spaces
    clean_string = re.sub(r"\s+", " ", input_string).strip()
    # remove all non-ascii characters
    clean_string = re.sub(r"[^\x00-\x7F]+", "", clean_string)
    # remove punctuation
    clean_string = re.sub(r"[^\w\s]", "", clean_string)
    # remove parentheses
    clean_string = re.sub(r'\([^)]*\)', '', clean_string)
    return clean_string


def find_title_and_geography(text_blocks, title, geography) -> Optional[str]:
    # Normalize title and geography outside the loop
    norm_title = normalise_text(title)
    norm_geography = normalise_text(geography)

    for i, text in enumerate(text_blocks):
        if norm_title in normalise_text(text):
            # Check if geography is in the current text block or the surrounding 2 text blocks
            for j in range(max(0, i - 2), min(len(text_blocks), i + 2)):
                if norm_geography in text_blocks[j]:
                    return text
    return None

def update_geography(geography_iso):
    if geography_iso == "EUR":
        geography_iso = "EUU"
    try:
        new_geography = pycountry.countries.get(alpha_3=geography_iso).name
    except LookupError:
        new_geography = iso_data.get(geography_iso)
    return new_geography

def check_document_geography(document_i, document_j):
    title_j = normalise_text(document_j.document_name)
    text_blocks = [passage for block in document_i.text_blocks for passage in block.text]

    # Rename empty values to None
    if document_j.document_metadata.geography == "nan":
        document_j.document_metadata.geography = None

    # If the mention document and the document have the same geography, high likelihood of real mention
    if document_i.document_metadata.geography_iso == document_j.document_metadata.geography_iso:
        for passage in text_blocks:
            if title_j.lower() in normalise_text(passage).lower():
                return passage
    else:
        return None

        # Check if the geography of the document is also mentioned in the text
        if not document_j.document_metadata.geography:
            # Try to grab missing geography name with ISO code
            new_geography = update_geography(document_j.document_metadata.geography_iso)
            document_j.document_metadata.geography = new_geography

        if document_j.document_metadata.geography:
            return find_title_and_geography(text_blocks, title_j, document_j.document_metadata.geography)
        else:
            for passage in text_blocks:
                if title_j in normalise_text(passage):
                    return passage

    return None
