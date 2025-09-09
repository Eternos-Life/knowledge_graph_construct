# Testing Directory

This directory contains all testing and development utilities for the Enhanced Digital Twin Agentic Framework.

## Directory Structure

### `/integration/`
Production-ready testing tools:
- `test_complete_framework.py` - Core framework integration test
- `test_all_s3_files.py` - Comprehensive S3 files testing tool

### `/experimental/`
Experimental and development test scripts:
- Various test files for specific components and features
- Prototype testing approaches
- Development validation scripts

### `/debug/`
Debug and analysis utilities:
- Debug scripts for troubleshooting
- Output analysis tools
- Development diagnostics

### `/archive/`
Historical documentation and artifacts:
- Previous version documentation
- Deployment manifests
- Legacy test results

## Usage

### Running Integration Tests
```bash
# Test the complete framework
python testing/integration/test_complete_framework.py

# Test all S3 files (with limits)
python testing/integration/test_all_s3_files.py --max-files 10

# Test specific customer files
python testing/integration/test_all_s3_files.py --customer "tim_wolff"
```

### Development Testing
Experimental tests are located in `/experimental/` and are used for:
- Component-specific testing
- Feature validation
- Performance analysis
- Development debugging

## Best Practices

1. **Integration tests** should be stable and production-ready
2. **Experimental tests** can be modified freely during development
3. **Debug tools** should be documented for team use
4. **Archive** maintains historical context but shouldn't be actively used

## Contributing

When adding new tests:
1. Place stable, reusable tests in `/integration/`
2. Place experimental/temporary tests in `/experimental/`
3. Document any new testing approaches
4. Update this README when adding new categories