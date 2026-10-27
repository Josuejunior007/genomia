from typing import List, Dict, Any

class RelationshipService:
  def __init__(self):

    pass

  def infer_implicit_relationships(self, schema_data: Dict[str, Any]) -> List[Dict[str, Any]]:

    suggestion = []

    tables = schema_data.get("tables", [])

    for table in tables:
      table_name = table.get("name")
      columns = table.get("columns", [])

      for column in columns:
        col_name = column.get("name")

        if col_name.endswitch("_id") and col_name != "id":
          referenced_table = col_name.replace("_id", "")
          suggestion.append({
            "source_table": table_name,
            "source_column": col_name,
            "target_table": referenced_table,
            "target_column": "id",
            "confidence_score": 0.85,
            "reason": "Inferido por correspondência de sufixo (_id) e nomenclatura de tabela."
          })
