from pathlib import Path
import pickle
import neomodel
import json
from collections import defaultdict
from src.models import FamilyNode, DocumentNode
from src.text import check_document_geography
from cpr_data_access.models import Dataset, CPRDocument
from src.neo4j import wait_for_neo4j, clear_neo4j
from rich.console import Console
from rich.progress import track

# load the dataset from disk if it exists, otherwise download it from huggingface
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

console = Console(
    highlight=False,
    log_path=False,
    color_system="auto",
    force_terminal=True,
)

# set up a connection to the neo4j database and clear whatever is there
neomodel.db.set_connection("bolt://neo4j:password@localhost:7687")
wait_for_neo4j()
clear_neo4j()

console.print("✔️ Loaded dataset!", style="bold green")

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

mentions_document = set()

for document_i in linking_progress_bar:
    for document_j in dataset:
        if document_i.document_id == document_j.document_id:
            continue
        if document_j.document_metadata.publication_ts < document_i.document_metadata.publication_ts:
            continue
        found_block = check_document_geography(document_i, document_j)
        if found_block:
            key = (document_i.document_id, document_j.document_id, document_j.document_name, found_block)
            if key not in mentions_document:
                if document_j.document_metadata.geography_iso != document_i.document_metadata.geography_iso:
                    console.print(
                        f"\n Found mention of [bold magenta]{document_j.document_name}[/bold magenta] "
                        f" {document_j.document_metadata} {document_j.translated} "
                        f"in [bold blue]{document_i.document_name}[/bold blue]"
                        f" {document_i.document_metadata.geography} {document_i.translated}",
                        end="\n",
                    )
                mentions_document.add(key)
                # console.print(
                #    f"Found mention of [bold magenta]{document_j.document_name}[/bold magenta] "
                #    f"in [bold blue]{document_i.document_id}[/bold blue]",
                #    end="\n",
                # )

mentions = list(mentions_document)

for id_i, id_j, name_j, found_block in mentions:
    node_i = DocumentNode.nodes.get(document_id=id_i)
    node_j = DocumentNode.nodes.get(document_id=id_j)
    node_i.mentions.connect(node_j)

# Organize mentions into a well-structured dictionary
structured_mentions = defaultdict(list)

for id_i, id_j, name_j, found_block in mentions:
    structured_mentions['mentions'].append({
        'document_id_i': id_i,
        'document_id_j': id_j,
        'document_name_j': name_j,
        'found_block': found_block
    })

# Save structured_mentions as a JSON file
with open('mentions.json', 'w') as json_file:
    json.dump(structured_mentions, json_file, indent=2)

console.print(
    "✔️ Connected all documents which mention each other!", style="bold green"
)
console.print("✔️ Done!", style="bold green")
