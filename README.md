# Policies mentioned in policies

I want to find out how often policies mention other policies. If we can make those connections, we might be able to draw an interesting graph.

I'm starting with a super simple approach: looking for exact matches of the titles of each policy in the text of every other policy. I expect there will be a lot of ways to improve the matching by incorporating more fuzzy methods, but this will provide us with a good baseline.

## Running the project locally

This project is orchestrated with docker. To build the containers, run `docker compose build`.

To populate the graph database with concepts and their properties/neighbours, run `docker compose run python populate_graph.py`.

To run the neo4j database, run `docker compose run neo4j`.

To shut everything down, run `docker compose down`.

## Inspecting the results

Make sure the neo4j container is running using the instructions above and then, when it's running, navigate to `http://localhost:7474/browser/`. Use the username `neo4j` and password `password` to log in. You should then be able to run cypher queries against the database.

If you just want an overview of a load of random relationships, run `MATCH p=()-->() WITH p, rand() AS r ORDER BY r RETURN p LIMIT 1000`.
