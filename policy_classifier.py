# Define the NER model and train it
import spacy
import json
import random
from spacy.training import offsets_to_biluo_tags
from spacy.training.example import Example
from spacy.matcher import Matcher, PhraseMatcher
from src.text import normalise_text
from spacy.language import Language
from spacy.tokens import Span

policy_keywords = ['accord', 'act', 'action', 'constitution',
                   'decision', 'decree', 'order', 'ordinance', 'directive',
                   'framework', 'law', 'plan', 'policy', 'programme', 'regulation',
                   'resolution', 'agenda', 'strategy', 'guideline', 'code', 'rule', 'procedure',
                   'protocol', 'standard', 'principle', 'requirement']

nlp = spacy.load("en_core_web_sm")

# Initialize PhraseMatcher
phrase_matcher = PhraseMatcher(nlp.vocab)

# Convert policy keywords to Doc objects for PhraseMatcher
policy_keyword_docs = [nlp(keyword.lower()) for keyword in policy_keywords]

# Add policy keyword patterns to PhraseMatcher
phrase_matcher.add("POLICY_KEYWORDS", None, *policy_keyword_docs)

@Language.component("match_policy_keywords")
def match_policy_keywords(doc):
    phrase_matches = phrase_matcher(doc)
    matcher_matches = matcher(doc)
    entities = []

    # Process matches from the PhraseMatcher
    for match_id, start, end in phrase_matches:
        span = Span(doc, start, end, label="POLICY")
        if not any(span.start >= ent.start and span.end <= ent.end for ent in entities):
            entities.append(span)

    # Set entities on the Doc
    doc.ents = entities
    return doc

nlp.add_pipe("match_policy_keywords", last=True)

# Path to your JSON file
json_file_path = "mentions.json"

# Read JSON data from the file
with open(json_file_path, "r") as json_file:
    training_data = json.load(json_file)

# Function to generate training data
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

# Create training data
all_data = create_training_data(training_data["mentions"])

# Shuffle the data to ensure randomness
random.shuffle(all_data)

# Define the ratios for train, validation, and test sets
train_ratio = 0.8
val_ratio = 0.1
test_ratio = 0.1

# Calculate the sizes of each set
total_samples = len(all_data)
train_size = int(total_samples * train_ratio)
val_size = int(total_samples * val_ratio)
test_size = total_samples - train_size - val_size

# Split the data into training, validation, and test sets
train_data = all_data[:train_size]
val_data = all_data[train_size:train_size + val_size]
test_data = all_data[train_size + val_size:]

# Train for a few epochs (increase if necessary)
for epoch in range(10):
    for text, annotations in train_data:
        example = Example.from_dict(nlp.make_doc(text), annotations)
        nlp.update([example], drop=0.5)  # Adjust the dropout rate as needed

# Save the trained model
nlp.to_disk("policy_ner_model")

# Load the trained model
trained_nlp = spacy.load("policy_ner_model")

# Evaluate the model on the validation data
total_correct = 0
total_predicted = 0
total_entities = 0

for text, annotations in val_data:
    doc = trained_nlp(text)

    # Extract the predicted entities
    predicted_entities = [(ent.start_char, ent.end_char, ent.label_) for ent in doc.ents]

    # Extract the ground truth entities
    ground_truth_entities = annotations['entities']

    # Calculate metrics
    correct_entities = set(predicted_entities) & set(ground_truth_entities)
    total_correct += len(correct_entities)
    total_predicted += len(predicted_entities)
    total_entities += len(ground_truth_entities)

# Calculate precision, recall, and F1 score
precision = total_correct / total_predicted if total_predicted > 0 else 0
recall = total_correct / total_entities if total_entities > 0 else 0
f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

print("Validation Precision:", precision)
print("Validation Recall:", recall)
print("Validation F1 Score:", f1_score)

# Evaluate the model on the test data
total_correct = 0
total_predicted = 0
total_entities = 0

for text, annotations in test_data:
    doc = trained_nlp(text)

    # Apply Matcher
    title_matches = matcher(doc)

    # Apply PhraseMatcher
    keyword_matches = phrase_matcher(doc)
    entities = annotations.get("entities", [])
    bilou_tags = offsets_to_biluo_tags(doc, entities)
    # Check for misaligned entities ('-')
    if '-' in bilou_tags:
        print("Misaligned entities in text:", text)
        print("Entities:", entities)
        print("BILOU tags:", bilou_tags)

    # Extract the predicted entities and BILOU tags
    predicted_entities = {(ent.start_char, ent.end_char) for ent in doc.ents}

    # Extract the ground truth entities
    ground_truth_entities = {(start, end) for start, end, _ in annotations['entities']}

    #for start, end, label in predicted_entities:
    #    if any(start <= match[1] <= end for match in title_matches):
    #        if any(start <= match[1] <= end for match in keyword_matches):
    #            filtered_entities.append((start, end, label))

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
    correct_entities = predicted_entities & ground_truth_entities
    total_correct += len(correct_entities)
    total_predicted += len(predicted_entities)
    total_entities += len(ground_truth_entities)

# Calculate precision, recall, and F1 score
precision = total_correct / total_predicted if total_predicted > 0 else 0
recall = total_correct / total_entities if total_entities > 0 else 0
f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

print("Precision:", precision)
print("Recall:", recall)
print("F1 Score:", f1_score)
