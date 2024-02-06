# Define the NER model and train it
import spacy
import json
from spacy.training.example import Example
from spacy.matcher import Matcher, PhraseMatcher
from src.text import normalise_text
from spacy.language import Language


policy_keywords = ['accord', 'act', 'action', 'constitution',
                   'decision', 'decree', 'order', 'ordinance', 'directive',
                   'framework', 'law', 'plan', 'policy', 'programme', 'regulation',
                   'resolution', 'agenda', 'strategy', 'guideline', 'code', 'rule', 'procedure',
                   'protocol', 'standard', 'principle', 'requirement']

# Load a blank English model
nlp = spacy.load("en_core_web_sm")
# Define the pattern to match phrases with at least two words where each word starts with an uppercase letter
pattern = [{"IS_TITLE": True, "OP": "+"}]

# Initialize Matcher and add the pattern
matcher = Matcher(nlp.vocab)
matcher.add("PHRASE_PATTERN", [pattern])

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
        span = doc[start:end]
        entities.append((span.start_char, span.end_char, "POLICY"))

    # Process matches from the Matcher
    for match_id, start, end in matcher_matches:
        span = doc[start:end]
        entities.append((span.start_char, span.end_char, "POLICY"))

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

        # Check if the policy is present in the text
        if policy and text:
            start_idx = text.lower().find(policy.lower())
            end_idx = start_idx + len(policy)
            # Check if the policy is at least one word and capitalized
            if start_idx != -1 and any(
                    keyword in policy.lower() for keyword in policy_keywords):
                entities = [(start_idx, end_idx, 'POLICY')]
                annotation = {'entities': entities}
                training_data.append((text, annotation))

    return training_data

# Create training data
all_data = create_training_data(training_data["mentions"])

# Split data into training and test sets
train_size = int(0.4 * len(all_data))  # 20 percent of the data
train_data = all_data[:train_size]  # Select the first 20 percent as training data
test_data = all_data[train_size:]   # The remaining data is for testing

# Train for a few epochs (increase if necessary)
for epoch in range(10):
    for text, annotations in train_data:
        start, end, label = annotations['entities'][0]
        entity_text = text[start:end]

        if start != end and entity_text.istitle() and any(
                keyword in entity_text.lower() for keyword in policy_keywords):
            example = Example.from_dict(nlp.make_doc(text), annotations)
            nlp.update([example], drop=0.5)  # Adjust the dropout rate as needed

# Save the trained model
nlp.to_disk("policy_ner_model")

# Load the trained model
trained_nlp = spacy.load("policy_ner_model")

# Evaluate the model on the test data
total_correct = 0
total_predicted = 0
total_entities = 0

for text, annotations in test_data:
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

print("Precision:", precision)
print("Recall:", recall)
print("F1 Score:", f1_score)
