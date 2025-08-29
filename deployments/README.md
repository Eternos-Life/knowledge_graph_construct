# Deployment Manifests

This directory contains deployment manifests that track version information for rollback purposes.

## Files

- `manifest-deploy-{timestamp}.json` - Deployment manifests with version information
- Each manifest contains:
  - Deployment ID and timestamp
  - Git commit hash
  - Function versions and aliases
  - Step Functions configuration

## Usage

### View Recent Deployments
```bash
ls -la deployments/
```

### Rollback to Previous Deployment
```bash
# Use the version management script
./scripts/manage_versions.sh rollback <function_name> <version>
```

### View Deployment History
```bash
# View specific manifest
cat deployments/manifest-deploy-{timestamp}.json
```

## Manifest Structure

```json
{
  "deployment_id": "deploy-1234567890",
  "timestamp": "2024-01-01T12:00:00",
  "environment": "dev",
  "region": "us-west-1",
  "git_commit": "abc1234",
  "functions": {
    "function-name": {
      "version": "5",
      "code_sha256": "...",
      "last_modified": "...",
      "aliases": {
        "LIVE": "5",
        "ROLLBACK": "4"
      }
    }
  }
}
```