# Policies mentioned in policies

We want to find instances where policy documents are mentioned by other policy documents. If we can make those connections, we might be able to draw an interesting citation graph for the climate policy space.

> [!WARNING]  
> This project is an experimental, and is not actively maintained! Users should not expect support when reproducing the project.

## Running the project locally

This project requires `docker` and `poetry`. If you don't have these installed, you can find instructions for installing them [here](https://docs.docker.com/get-docker/) and [here](https://python-poetry.org/docs/).

### Running the neo4j container

To run the neo4j container, navigate to the root of the project and run `docker-compose up -d`. This will start a neo4j container running on `http://localhost:7474`. You can log in with the username `neo4j` and password `password`.

### Running the mention-finding pipeline

To run the project, navigate to the root of the project and run `poetry install` to install the dependencies. Then, run `poetry run python main.py` to run the project.

## Inspecting the results

Make sure the neo4j container is running using the instructions above and then, when it's running, navigate to `http://localhost:7474/browser/`. Use the username `neo4j` and password `password` to log in. You should then be able to run cypher queries against the database.

If you just want an overview of a load of random relationships, run `MATCH p=()-->() WITH p, rand() AS r ORDER BY r RETURN p LIMIT 1000`.

## Writeups

See the [writeups directory](writeups/) for more information on the project and its development history.
