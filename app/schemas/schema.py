from pydantic import BaseModel, Field

class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: str | None = None
    is_primary_key: bool = False

class ForeignKeyInfo(BaseModel):
    constrained_columns: list[str]
    referred_table: str
    referred_schema: str = "public"
    referred_columns: list[str]

class IndexInfo(BaseModel):
    name: str
    column_names: list[str]
    unique: bool

class TableInfo(BaseModel):
    name: str
    schema: str = "public"
    columns: list[ColumnInfo]
    primary_key: list[str]
    foreign_keys: list[ForeignKeyInfo]
    indexes: list[IndexInfo]

class SchemaSnapshot(BaseModel):
    database: str
    schema: str
    tables: list[TableInfo]

class Recommendation(BaseModel):
    severity: str = Field(pattern="^(low|medium|high)$")
    table: str
    category: str
    message: str
    suggested_sql: str | None = None
    evidence: str | None = None

class AnalysisReport(BaseModel):
    summary: str
    tables_analyzed: int
    recommendations: list[Recommendation]

class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    comment: str = Field(default="", max_length=500)

class ReviewItem(BaseModel):
    id: int
    table: str
    kind: str
    description: str
    confidence: float
    status: str = "pending"
    rationale: str

class ReviewResponse(BaseModel):
    id: int
    status: str
    comment: str
