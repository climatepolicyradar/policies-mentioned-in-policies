## Running the project locally

This project is orchestrated with docker. To build the containers, run `docker-compose up -d`.

To run the neo4j database and the code, run `python main.py`.

## Updates

The goal here is to reject a bunch of spurious matches.

I've included these checks to do so:

* Check that the publication date of the document mentioned is prior to the publication date of the document it is mentioned in
* Remove ability to self-mentions or duplicates
* Don't remove capitalization + remove parentheses and what's in them in titles
* Explore how important date is in matching (trivial number of examples in the entire corpus where title and geography are the same and the date is different)
* Create logic to check geography: We want to check if geography matches and if it does, it is way more likely to be a real mention. If geography doesn't match, then I've created logic to fill in geography (if it is missing) and check for the geography name in addition to the title in the text block that the mention is in as well as the surrounding few text blocks.

The mentions from this are then exported into a json that includes document ids and the text block where the mention was found. 
This json will be used to train/test the classifier in the PR coming up. 