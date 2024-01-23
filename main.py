from pathlib import Path
import pickle
import neomodel
from src.models import FamilyNode, DocumentNode
from src.text import normalise_text, check_document_geography
from cpr_data_access.models import Dataset, CPRDocument
from src.neo4j import wait_for_neo4j, clear_neo4j
from rich.console import Console
from rich.progress import track

console = Console(
    highlight=False,
    log_path=False,
    color_system="auto",
    force_terminal=True,
)

# set up a connection to the neo4j database and clear whatever is there
neomodel.db.set_connection("bolt://neo4j:password@localhost:7689")
wait_for_neo4j()
clear_neo4j()


# load the dataset from disk if it exists, otherwise download it from huggingface
dataset_path = Path("data/dataset.pkl")
if dataset_path.exists():
    with console.status("Loading dataset from disk..."):
        with open(dataset_path, "rb") as f:
            dataset = pickle.load(f)
else:
    with console.status("Loading dataset from huggingface..."):
        dataset = Dataset(
            CPRDocument, cdn_domain="cdn.climatepolicyradar.org"
        ).from_huggingface()
    with console.status("Saving dataset to disk for future runs..."):
        with open(dataset_path, "wb") as f:
            pickle.dump(dataset, f)

console.print("✔️ Loaded dataset!", style="bold green")

#dataset = dataset[:700]

# create the nodes for the families and documents
node_creation_progress_bar = track(
    dataset, description="Creating documents and families...", transient=True
)

for document in node_creation_progress_bar:
    document_node = DocumentNode.get_or_create(
        {
            "document_id": document.document_id,
            "document_name": document.document_name,
        }
    )[0]

    if document.document_metadata is not None:
        family_node = FamilyNode.get_or_create(
            {
                "family_id": document.document_metadata.family_id,
                "family_name": document.document_metadata.family_name,
            },
        )[0]
        document_node.family.connect(family_node)

console.print("✔️ Created documents and families!", style="bold green")

# create links between documents which mention each other
linking_progress_bar = track(
    dataset,
    description="Looking for mentions of policies in other policies...",
    transient=True,
)

import pandas as pd

# Replace 'your_data' with your actual dataset
df = pd.DataFrame({
    'title': [document.document_name for document in dataset],
    'country': [document.document_metadata.geography_iso for document in dataset],
    'date': [document.document_metadata.publication_ts for document in dataset]
})

# Find duplicates based on country and title, but different dates
different_dates_duplicates = df[df.duplicated(['country', 'title'], keep=False) & ~df.duplicated(['country', 'title', 'date'], keep=False)]

# Display the instances with duplicate country and title, but different dates
print(different_dates_duplicates)

mentions = []
for document_i in linking_progress_bar:
    for document_j in dataset:
        if document_i.document_id == document_j.document_id:
            continue
        if (check_document_geography(document_i, document_j)
                # Check if mentioned document was published before the document it is mentioned in
                and (document_j.document_metadata.publication_ts < document_i.document_metadata.publication_ts)
                # Only show unique mentions
                and (document_i.document_name, document_j.document_name) not in mentions):
            node_i = DocumentNode.nodes.get(document_id=document_i.document_id)
            node_j = DocumentNode.nodes.get(document_id=document_j.document_id)
            node_i.mentions.connect(node_j)
            if document_j.document_metadata.geography_iso is not document_i.document_metadata.geography_iso:
                console.print(
                    f"\n Found mention of [bold magenta]{document_j.document_name}[/bold magenta] "
                    f" {document_j.document_metadata} {document_j.translated} "
                    f"in [bold blue]{document_i.document_name}[/bold blue]"
                    f" {document_i.document_metadata.geography} {document_i.translated}",
                    end="\n",
                )
            mentions.append((document_i.document_name, document_j.document_name))

console.print(len(mentions))
for found_in_title, title in mentions:
    console.print(
        f"Found mention of [bold magenta]{title}[/bold magenta] "
        f"in [bold blue]{found_in_title}[/bold blue]",
        end="\n",
    )


console.print(
    "✔️ Connected all documents which mention each other!", style="bold green"
)
console.print("✔️ Done!", style="bold green")


# Create training data out of documents mentioned and the things they are mentioned in

# Define the NER model and train it
import spacy
from spacy.training.example import Example

# Load a blank English model
nlp = spacy.blank("en")

# Add NER to the pipeline
ner = nlp.add_pipe("ner")

# Add the 'POLICY' label to the NER model
ner.add_label("POLICY")

# Train the model
nlp.begin_training()

# Train for a few epochs (increase if necessary)
for epoch in range(10):
    for text, annotations in training_data:
        # Check if the annotated entity is more than one word and capitalized
        if annotations['entities'][0][0] != annotations['entities'][0][1] and text[annotations['entities'][0][0]:annotations['entities'][0][1]].istitle():
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
