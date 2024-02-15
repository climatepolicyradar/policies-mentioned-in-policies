import spacy
import json
import random
from spacy.training import offsets_to_biluo_tags
from spacy.training.example import Example
from spacy.matcher import Matcher, PhraseMatcher
from src.text import normalise_text
from spacy.language import Language
from spacy.tokens import Span

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

def get_data():
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

    for text, annotations in test_data:
        doc = trained_nlp(text)

        # Check for misaligned entities ('-')
        bilou_tags = offsets_to_biluo_tags(doc, annotations.get("entities", []))
        if '-' in bilou_tags:
            print("Misaligned entities in text:", text)
            print("Entities:", entities)
            print("BILOU tags:", bilou_tags)

        # Extract the predicted entities
        predicted_entities = {(ent.start_char, ent.end_char) for ent in doc.ents}

        # Extract the ground truth entities
        ground_truth_entities = {(start, end) for start, end, _ in annotations['entities']}

        #print("Found Blocks:")
        #print(text)
        #print("Predicted Entities:")
        #for entity in predicted_entities:
        #    print(text[entity[0]:entity[1]])
        #print("Ground Truth Entities:")
        #for entity in ground_truth_entities:
        #    print(text[entity[0]:entity[1]])
        #print("=" * 50)

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


all_data = get_data()

train_ratio = .8
train_size = int(len(all_data) * train_ratio)
train_data = all_data[:train_size]
# train_model(train_data)

# Load the trained model
trained_nlp = spacy.load("policy_ner_model")

val_ratio = 0.1
val_size = int(len(all_data) * val_ratio)
val_data = all_data[train_size:train_size + val_size]

test_model(trained_nlp, "validation", val_data)

test_data = all_data[int(len(all_data) * (train_ratio + val_ratio)):]
test_model(trained_nlp, "test", test_data)