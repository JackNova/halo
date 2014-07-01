from relationships import Relationships
from relationshipstats import RelationshipStats
from history import History

Relationships.create_table(fail_silently=True)
RelationshipStats.create_table(fail_silently=True)
History.create_table(fail_silently=True)
