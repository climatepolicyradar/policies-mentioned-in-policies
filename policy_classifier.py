# Define the NER model and train it
import spacy
from spacy.training.example import Example
import pandas as pd
from src.text import normalise_text

policy_keywords = ['accord', 'act', 'action', 'constitution',
                   'decision', 'decree', 'order', 'ordinance', 'directive',
                   'framework', 'law', 'plan', 'policy', 'programme', 'regulation',
                   'resolution', 'agenda', 'strategy', 'guideline', 'code', 'rule', 'procedure',
                   'protocol', 'standard', 'principle', 'requirement']

# Load a blank English model
nlp = spacy.blank("en")

# Add NER to the pipeline
ner = nlp.add_pipe("ner")

# Add the 'POLICY' label to the NER model
ner.add_label("POLICY")

# Train the model
nlp.begin_training()

training_data = pd.read_csv("output.csv")

# Function to generate training data
def create_training_data(dataframe):
    training_data = []

    for index, row in dataframe.iterrows():
        text = normalise_text(row.iloc[2])
        policy = normalise_text(row.iloc[1])

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
training_data = create_training_data(training_data)
print(training_data)

# Train for a few epochs (increase if necessary)
for epoch in range(10):
    for text, annotations in training_data:
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

policy_mentions_ner = []

# replace text_blocks with each documents and their text
for text in text_blocks:
    doc = trained_nlp(text)
    policy_entities = [ent.text for ent in doc.ents if ent.label_ == 'POLICY']
    policy_mentions_ner.extend(policy_entities)

print("Policy Mentions:", policy_mentions_ner)
