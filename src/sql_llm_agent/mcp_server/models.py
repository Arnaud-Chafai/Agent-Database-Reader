from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class SQLQueryRequest:
    """Solicitud de consulta SQL para MCP"""
    query: str
    limit: Optional[int] = 100

@dataclass 
class SQLQueryResult:
    """Resultado de consulta SQL para MCP"""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    rows_affected: int = 0
    
    def to_text(self) -> str:
        """Convertir resultado a texto para MCP"""
        if not self.success:
            return f"❌ Error: {self.error}"
        
        if not self.data:
            return "✅ Consulta ejecutada exitosamente, sin resultados"
        
        import json
        return json.dumps(self.data, indent=2, default=str, ensure_ascii=False)