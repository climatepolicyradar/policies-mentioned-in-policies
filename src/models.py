from neomodel import StructuredNode, StringProperty, RelationshipFrom, RelationshipTo

class FamilyNode(StructuredNode):
    family_id = StringProperty(unique_index=True)
    title = StringProperty()
    documents = RelationshipFrom('DocumentNode', 'BELONGS_TO')


class DocumentNode(StructuredNode):
    document_id = StringProperty(unique_index=True)
    name = StringProperty()
    family = RelationshipTo('FamilyNode', 'BELONGS_TO')
    mentions = RelationshipTo('DocumentNode', 'MENTIONS')
