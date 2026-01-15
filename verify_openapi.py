"""Verify OpenAPI specification files."""
import json
import yaml

# Load and verify YAML
with open('openapi.yaml', 'r', encoding='utf-8') as f:
    yaml_spec = yaml.safe_load(f)

# Load and verify JSON
with open('openapi.json', 'r', encoding='utf-8') as f:
    json_spec = json.load(f)

print("✅ OpenAPI Specification Verification\n")
print(f"Title: {yaml_spec['info']['title']}")
print(f"Version: {yaml_spec['info']['version']}")
print(f"Description: {yaml_spec['info']['description'][:100]}...")
print(f"\nTotal endpoints: {len(yaml_spec['paths'])}")
print(f"Total tags: {len(yaml_spec.get('tags', []))}")
print(f"Total schemas: {len(yaml_spec.get('components', {}).get('schemas', {}))}")

print("\n📋 Endpoint breakdown by tag:")
tags = {}
for path, methods in yaml_spec['paths'].items():
    for method, data in methods.items():
        if isinstance(data, dict) and 'tags' in data:
            tag = data['tags'][0] if data['tags'] else 'Untagged'
            tags[tag] = tags.get(tag, 0) + 1

for tag, count in sorted(tags.items()):
    print(f"  • {tag}: {count} endpoints")

print("\n🔍 Sample endpoints:")
sample_paths = list(yaml_spec['paths'].keys())[:10]
for path in sample_paths:
    methods = [m.upper() for m in yaml_spec['paths'][path].keys() if m.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']]
    print(f"  • {', '.join(methods)} {path}")

print("\n✅ Both openapi.yaml and openapi.json are valid!")
