import spacy
import json
import random
from fuzzywuzzy import fuzz
from src.text import update_geography
from spacy.training import offsets_to_biluo_tags
from spacy.training.example import Example
from spacy.matcher import Matcher, PhraseMatcher
from src.text import normalise_text
from spacy.language import Language
from spacy.tokens import Span

from pathlib import Path
import pickle
from cpr_data_access.models import Dataset, CPRDocument
from src.neo4j import wait_for_neo4j, clear_neo4j


@Language.component("match_policy_keywords")
def match_policy_keywords(doc):
    phrase_matches = phrase_matcher(doc)
    entities = []

    # Process matches from the PhraseMatcher
    for match_id, start, end in phrase_matches:
        span = Span(doc, start, end, label="POLICY")
        if not any(span.start >= ent.start and span.end <= ent.end for ent in entities):
            entities.append(span)

    # Set entities on the Doc
    doc.ents = entities
    return doc

def add_policy_matcher(nlp):
    policy_keywords = ['accord', 'act', 'action', 'constitution',
                       'decision', 'decree', 'order', 'ordinance', 'directive',
                       'framework', 'law', 'plan', 'policy', 'programme', 'regulation',
                       'resolution', 'agenda', 'strategy', 'guideline', 'code', 'rule', 'procedure',
                       'protocol', 'standard', 'principle', 'requirement']

    # Initialize PhraseMatcher
    phrase_matcher = PhraseMatcher(nlp.vocab)

    # Convert policy keywords to Doc objects for PhraseMatcher
    policy_keyword_docs = [nlp(keyword.lower()) for keyword in policy_keywords]

    # Add policy keyword patterns to PhraseMatcher
    phrase_matcher.add("POLICY_KEYWORDS", None, *policy_keyword_docs)

    return phrase_matcher

def create_training_data(data):
    training_data = []

    for entry in data:
        text = normalise_text(entry.get("found_block", ""))
        policy = normalise_text(entry.get("document_name_j", ""))

        if policy and text:
            start_idx = text.lower().find(policy.lower())
            end_idx = start_idx + len(policy)

            # Account for if the same title shows up multiple times in a text block
            if end_idx < len(text) and text[end_idx].isalnum():
                continue

            while start_idx != -1:
                entities = [(start_idx, end_idx, 'POLICY')]
                annotation = {'entities': entities}
                training_data.append((text, annotation))
                start_idx = text.lower().find(policy.lower(), start_idx + 1)

    return training_data

def get_model_data():
    # Path to your JSON file
    json_file_path = "mentions.json"

    # Read JSON data from the file
    with open(json_file_path, "r") as json_file:
        training_data = json.load(json_file)

    # Create training data
    all_data = create_training_data(training_data["mentions"])

    return all_data

def train_model(train_data):
    nlp = spacy.load("en_core_web_sm")

    #phrase_matcher = add_policy_matcher(nlp)
    #nlp.add_pipe("match_policy_keywords", last=True)

    # Train for a few epochs
    for epoch in range(10):
        for text, annotations in train_data:
            example = Example.from_dict(nlp.make_doc(text), annotations)
            nlp.update([example], drop=0.5)

    # Save the trained model
    nlp.to_disk("policy_ner_model")

def test_model(trained_nlp, stage, test_data):

    total_correct = 0
    total_predicted = 0
    total_entities = 0
    predicted_titles = []

    nlp_countries = spacy.load("en_core_web_sm")

    countries_for_titles = {}
    for text, annotations in test_data:
        doc = trained_nlp(text)

        # Check for misaligned entities ('-')
        bilou_tags = offsets_to_biluo_tags(doc, annotations.get("entities", []))
        if '-' in bilou_tags:
            print("Misaligned entities in text:", text)
            print("BILOU tags:", bilou_tags)

        # Extract the predicted entities
        predicted_entities = {(ent.start_char, ent.end_char) for ent in doc.ents}

        # Extract the ground truth entities
        ground_truth_entities = {(start, end) for start, end, _ in annotations['entities']}

        doc = nlp_countries(text)
        # Extract country names using NER
        countries = set()
        for ent in doc.ents:
            if ent.label_ in ["GPE", "LOC"]:
                countries.add(ent.text)

        for entity in predicted_entities:
            predicted_titles.append(text[entity[0]:entity[1]])
            countries_for_titles[text[entity[0]:entity[1]]] = countries

        # Calculate metrics
        correct_entities = 0
        for ground_truth_entity in ground_truth_entities:
            for predicted_entity in predicted_entities:
                if set(range(ground_truth_entity[0], ground_truth_entity[1])).issubset(
                        set(range(predicted_entity[0], predicted_entity[1]))):
                    correct_entities += 1
                    break  # Stop searching for this ground truth entity once it's found in a predicted entity

        total_correct += correct_entities
        total_predicted += len(predicted_entities)
        total_entities += len(ground_truth_entities)

    # Calculate precision, recall, and F1 score
    precision = total_correct / total_predicted if total_predicted > 0 else 0
    recall = total_correct / total_entities if total_entities > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print(stage, " Precision:", precision)
    print(stage, " Recall:", recall)
    print(stage, " F1 Score:", f1_score)

    return predicted_titles, countries_for_titles

def load_documents():
    dataset_path = Path("data/dataset.pkl")
    if dataset_path.exists():
        with open(dataset_path, "rb") as f:
            dataset = pickle.load(f)
    else:
        dataset = Dataset(
            CPRDocument, cdn_domain="cdn.climatepolicyradar.org"
        ).from_huggingface()
        with open(dataset_path, "wb") as f:
            pickle.dump(dataset, f)
    return dataset

def fuzzy_match_titles(model_titles, database, countries_check, threshold=90):
    matched_titles = {}

    easy_match = 0
    difficult_match = 0

    # Sort through found titles
    for model_title in model_titles:
        potential_matches = []

        # If matches above 90% in the text block then add it as a potential match
        for document in database:
            score = fuzz.ratio(model_title.lower(), document.document_name.lower())
            if score >= threshold:
                if (document.document_name, document.document_metadata.geography_iso, document.document_metadata.geography, document.document_metadata.publication_ts, score) not in potential_matches:
                    potential_matches.append((document.document_name, document.document_metadata.geography_iso, document.document_metadata.geography, document.document_metadata.publication_ts, score))

        # Sort matches and grab all the matches with the top score
        if potential_matches:
            potential_matches.sort(key=lambda x: x[4], reverse=True)
            # Keep only the top scoring matches
            top_score = potential_matches[0][4]
            top_matches = [match for match in potential_matches if match[4] == top_score]

            if len(top_matches) == 1:
                easy_match += 1
            else:
                # Attempt to disambiguate
                if countries_check[model_title]:
                    # Check if country name is mentioned in the text block
                    country_name = list(countries_check[model_title])[0]

                    # Match country name mentioned to country of document
                    for match in top_matches:
                        title_geography = match[2]
                        if title_geography == "nan":
                            # Try to grab missing geography name with ISO code
                            new_geography = update_geography(match[1])
                            title_geography = new_geography

                        if title_geography == country_name:
                            top_matches = [match]
                            break

                # Sometimes a country will have a geography iso, but not a name
                # So here, filter out duplicates, irrespective of country name
                filtered_top_matches = []
                seen_tuples = set()

                for top_match in top_matches:
                    key = top_match[:2] + top_match[3:]
                    if key not in seen_tuples:
                        filtered_top_matches.append(top_match)
                        seen_tuples.add(key)

                top_matches = filtered_top_matches

                if len(top_matches) == 1:
                    easy_match += 1
                else:
                    # Print out those that have not been disambiguated
                    print(model_title)
                    print(top_matches)
                    difficult_match += 1

            # Add matches to matches titles
            matched_titles[model_title] = top_matches

    return matched_titles, easy_match, difficult_match

# Load the model training and test data
all_data = get_model_data()

# Train model
train_ratio = .8
train_size = int(len(all_data) * train_ratio)
train_data = all_data[:train_size]
#train_model(train_data)

# Load the trained model
trained_nlp = spacy.load("policy_ner_model")

# Validate model
val_ratio = 0.1
val_size = int(len(all_data) * val_ratio)
val_data = all_data[train_size:train_size + val_size]
val_titles, validation_for_titles = test_model(trained_nlp, "validation", val_data)

# Test model
test_data = all_data[int(len(all_data) * (train_ratio + val_ratio)):]
test_titles, test_for_titles = test_model(trained_nlp, "test", test_data)

# Match model outputs with our document titles
dataset = load_documents()
matched_titles, easy_matches, difficult_matches = fuzzy_match_titles(test_titles, dataset, test_for_titles)

print("Policies found in text:", len(test_titles))
print("Policies matching ours:", easy_matches)
print("Policies matching ours, but can't disambiguate:", difficult_matches)
print("Policies found, but not matches:", len(test_titles) - easy_matches - difficult_matches)