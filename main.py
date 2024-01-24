from pathlib import Path
import pickle
import neomodel
import csv
import concurrent.futures
from multiprocessing import Manager
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

#dataset = dataset[:200]

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

def process_document(document_i, dataset, progress_list):
    mentions = []

    for document_j in dataset:
        if document_i.document_id == document_j.document_id:
            continue

        if document_j.document_metadata.publication_ts < document_i.document_metadata.publication_ts:
            exists, found_block = check_document_geography(document_i, document_j)

            if exists and (document_i.document_name, document_j.document_name, found_block) not in mentions:
                node_i = DocumentNode.nodes.get(document_id=document_i.document_id)
                node_j = DocumentNode.nodes.get(document_id=document_j.document_id)
                node_i.mentions.connect(node_j)

                if document_j.document_metadata.geography_iso != document_i.document_metadata.geography_iso:
                    console.print(
                        f"\n Found mention of [bold magenta]{document_j.document_name}[/bold magenta] "
                        f" {document_j.document_metadata} {document_j.translated} "
                        f"in [bold blue]{document_i.document_name}[/bold blue]"
                        f" {document_i.document_metadata.geography} {document_i.translated}",
                        end="\n",
                    )
                mentions.append((document_i.document_name, document_j.document_name, found_block))
    # Update progress
    progress_list.append(1)
    console.print(f"Document {document_i.document_name} mentions: {len(mentions)}")

    return mentions

def parallel_process_documents(dataset):
    mentions = []
    if __name__ == '__main__':
        with Manager() as manager:
            progress_list = manager.list()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Process documents in parallel
                futures = [executor.submit(process_document, document_i, dataset, progress_list) for document_i in linking_progress_bar]
                # Wait for all threads to finish
                concurrent.futures.wait(futures)

            # Combine the results from all processed documents
            for future in concurrent.futures.as_completed(futures):
                mentions.extend(future.result())

    return mentions

# Call the parallel processing function
mentions = parallel_process_documents(dataset)

console.print(len(mentions))
for found_in_title, title, found_block in mentions:
    console.print(
        f"Found mention of [bold magenta]{title}[/bold magenta] "
        f"in [bold blue]{found_in_title}[/bold blue]",
        end="\n",
    )

# Specify the file name
csv_file = 'output.csv'

# Write the list of tuples to a CSV file
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerows(mentions)


console.print(
    "✔️ Connected all documents which mention each other!", style="bold green"
)
console.print("✔️ Done!", style="bold green")