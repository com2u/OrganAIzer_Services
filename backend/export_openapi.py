"""
Export OpenAPI specification from FastAPI app.
Generates both openapi.yaml and openapi.json files in the repository root.
"""

import json
import yaml
import sys
import os
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Import the FastAPI app
from main import app

def export_openapi():
    """Export OpenAPI spec to YAML and JSON files."""
    
    # Get the OpenAPI schema from FastAPI
    openapi_schema = app.openapi()
    
    # Repository root is parent of backend directory
    repo_root = backend_dir.parent
    
    # Export to YAML
    yaml_path = repo_root / "openapi.yaml"
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(openapi_schema, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    print(f"✅ Exported OpenAPI spec to: {yaml_path}")
    
    # Export to JSON
    json_path = repo_root / "openapi.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
    print(f"✅ Exported OpenAPI spec to: {json_path}")
    
    # Print summary
    print(f"\n📊 OpenAPI Spec Summary:")
    print(f"  Title: {openapi_schema['info']['title']}")
    print(f"  Version: {openapi_schema['info']['version']}")
    print(f"  Endpoints: {len(openapi_schema['paths'])} paths")
    print(f"  Tags: {len(openapi_schema.get('tags', []))} tags")
    print(f"  Components/Schemas: {len(openapi_schema.get('components', {}).get('schemas', {}))}")


if __name__ == "__main__":
    export_openapi()
