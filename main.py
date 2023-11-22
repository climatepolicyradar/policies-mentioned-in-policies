from pathlib import Path
import pickle
import neomodel
from src.models import FamilyNode, DocumentNode
from src.text import normalise_text
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
neomodel.db.set_connection("bolt://neo4j:password@localhost:7687")
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

mentions = []
for document_i in linking_progress_bar:
    full_text_i = " ".join(
        [passasge for block in document_i.text_blocks for passasge in block.text]
    )
    full_text_i = normalise_text(full_text_i)
    for document_j in dataset:
        if document_i.document_id == document_j.document_id:
            continue
        title_j = normalise_text(document_j.document_name)
        if title_j in full_text_i:
            node_i = DocumentNode.nodes.get(document_id=document_i.document_id)
            node_j = DocumentNode.nodes.get(document_id=document_j.document_id)
            node_i.mentions.connect(node_j)
            mentions.append((document_i.document_name, document_j.document_name))

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
