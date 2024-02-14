## Running the project locally

This project is orchestrated with docker. To build the containers, run `docker-compose up -d`.

To run the neo4j database and the code, run `python main.py`.

## Main file

The goal here to detect mentions of our titles in our texts and reject a bunch of spurious matches.

I've included these checks to do so:

* Check that the publication date of the document mentioned is prior to the publication date of the document it is mentioned in
* Remove ability to self-mentions or duplicates
* Don't remove capitalization + remove parentheses and what's in them in titles
* Explore how important date is in matching (trivial number of examples in the entire corpus where title and geography are the same and the date is different)
* Create logic to check geography: We want to check if geography matches and if it does, it is way more likely to be a real mention. If geography doesn't match, then I've created logic to fill in geography (if it is missing) and check for the geography name in addition to the title in the text block that the mention is in as well as the surrounding few text blocks.

The mentions from this are then exported into a json that includes document ids and the text block where the mention was found. 
This json will be used to train/test the classifier in the PR coming up. 

## Policy Classifier

### NER model 

Made the baseline code more efficient and removed parts to be able to run on the whole corpus and get data for the NER model
Created (trained, validated, tested) basic NER model

### Entity Disambiguation

1. Load in data of our documents
2. Fuzzy match found titles to titles of our documents
3. Narrow down to top matches
4. When there are multiple matches, try to detect geography mentioned in text block and match based on that as well
5. Adding in GST and running model on that data to see performance.

## What problems have I not addressed?

I originally tried to set more strict rules for the model such 
as requiring capitalization in titles and necessitating that titles 
must include at least one of a list of key policy words. I found this to be too restrictive,
but some different combination of rule setting might improve model performance. See work done previously [here](https://linear.app/climate-policy-radar/issue/RND-885/test-if-defining-specific-rules-for-ner-is-useful).

Right now, we are just returning None instead of running through the logic in this else statement 
because it takes too long to run and check if the geography is also mentioned in the text block window. 
The result of this is that are training/test set (mentions.json) only contains examples where the geography 
of the document and the mention are the same (this excludes a small but non-trivial number of examples). Ticket [here](https://linear.app/climate-policy-radar/issue/RND-898/incorporate-check-of-geography-to-create-test-set).


