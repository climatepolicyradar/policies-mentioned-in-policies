from rich.console import Console
import time
import neomodel

def clear_neo4j():
    neomodel.db.cypher_query('MATCH (n) DETACH DELETE n')


def ping():
    try:
        neomodel.db.cypher_query("MATCH (n) RETURN n LIMIT 1")
        return True
    except:
        return False


def wait_for_neo4j():
    with Console().status("Waiting for neo4j to start..."):
        while not ping():
            time.sleep(1)
