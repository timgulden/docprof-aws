# Docker Installation Check

**Date**: 2025-12-10

## Current Status

The Cursor Docker extension is installed, but Docker Desktop is **not yet available** at the command line.

## What's Needed

The Cursor Docker extension is a **UI tool** for managing Docker containers/images through Cursor's interface. However, our Lambda layer build script needs **Docker Desktop** installed and running, which provides the `docker` command-line tool.

## Two Options

### Option 1: Install Docker Desktop (Recommended) ✅

**Why**: Provides the `docker` command needed by our build script.

**Steps**:
1. Download Docker Desktop: https://www.docker.com/products/docker-desktop
2. Install Docker Desktop
3. Launch Docker Desktop (wait for it to start)
4. Verify: `docker --version` should work

**Then**: Our build script will work automatically!

### Option 2: Use Cursor Docker Extension

If the Cursor extension can provide Docker functionality, we might be able to:
- Use Cursor's Docker integration
- Or configure the build script to use Cursor's Docker interface

**Note**: This would require modifying our build approach.

## Quick Check

Run this to see if Docker Desktop is installed:

```bash
# Check if Docker Desktop app exists
ls -la /Applications/ | grep -i docker

# Check common Docker paths
/usr/local/bin/docker --version
/opt/homebrew/bin/docker --version
```

## Next Steps

1. **If Docker Desktop is installed**: Start it and verify `docker --version` works
2. **If not installed**: Install Docker Desktop (see Option 1)
3. **Once Docker works**: Run `terraform apply` - the layer will build automatically!

## Testing

Once Docker is available:

```bash
cd terraform/modules/lambda-layer
./build_layer_docker.sh requirements.txt /tmp/test-layer
```

This should build the Lambda layer successfully.

