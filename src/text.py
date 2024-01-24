import re
import pycountry
import pandas as pd

csv_url = "https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes/raw/master/all/all.csv"
iso_df = pd.read_csv(csv_url)


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


def find_title_and_geography(text_blocks, title, geography):
    for i, text in enumerate(text_blocks):
        if title in text:
            # Check if geography is in the current text block or the surrounding 3 text blocks
            for j in range(max(0, i - 3), min(len(text_blocks), i + 4)):
                if geography in text_blocks[j]:
                    return True, text_blocks[j]
    return False, ""


def update_geography(document_j):
    new_geography = "nan"
    geography_iso = document_j.document_metadata.geography_iso
    if geography_iso == "EUR":
        geography_iso = "EUU"
    try:
        new = pycountry.countries.get(alpha_3=geography_iso)
        if new:
            return new.name
    except LookupError:
        # Find the corresponding row based on geography_iso in the alpha-3 column
        iso_row = iso_df[iso_df['alpha-3'] == geography_iso]

        if not iso_row.empty:
            # Grab the value from the "name" column
            new_geography = iso_row.iloc[0]['name']

    return new_geography


def check_document_geography(document_i, document_j):
    full_text_i = " ".join(
        [passage for block in document_i.text_blocks for passage in block.text]
    )
    full_text_i = normalise_text(full_text_i)
    title_j = normalise_text(document_j.document_name)

    # If the mention document and the document have the same geography, high likelihood of real mention
    if document_i.document_metadata.geography_iso == document_j.document_metadata.geography_iso:
        for block in document_i.text_blocks:
            for passage in block.text:
                text_i = normalise_text(passage).lower()
                if title_j.lower() in text_i:
                    return True, text_i
    else:
        # Check if the geography of the document is also mentioned in the text
        if document_j.document_metadata.geography == "nan":
            # Try to grab missing geography name with ISO code
            new_geography = update_geography(document_j)
            document_j.document_metadata.geography = new_geography

        if document_j.document_metadata.geography != "nan":
            text_blocks = [passage for block in document_i.text_blocks for passage in block.text]
            return find_title_and_geography(text_blocks, title_j, document_j.document_metadata.geography)
        else:
            for block in document_i.text_blocks:
                for passage in block.text:
                    text_i = normalise_text(passage)
                    if title_j in text_i:
                        return True, text_i

    return False, ""
