from typing import List, Dict, Any
import re

class StandardizationService:
    def __init__(self):
        
        self.snake_case_pattern = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")

    def validate_naming(self, schema_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        
        issues = []
        tables = schema_data.get("tables", [])

        for table in tables:
            table_name = table.get("name")
            
            
            if not self.snake_case_pattern.match(table_name):
                issues.append({
                    "target_type": "table",
                    "name": table_name,
                    "issue": "O nome da tabela não segue o padrão snake_case.",
                    "suggested_fix": table_name.lower().replace(" ", "_")
                })

            
            for column in table.get("columns", []):
                col_name = column.get("name")
                if not self.snake_case_pattern.match(col_name):
                    issues.append({
                        "target_type": "column",
                        "table": table_name,
                        "name": col_name,
                        "issue": "O nome da coluna não segue o padrão snake_case.",
                        "suggested_fix": col_name.lower().replace(" ", "_")
                    })

        return issues