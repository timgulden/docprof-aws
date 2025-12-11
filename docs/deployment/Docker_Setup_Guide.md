# Docker Setup Guide for Lambda Layer Build

**Date**: 2025-12-10  
**Purpose**: Set up Docker to build Lambda layers with C extensions

## Why Docker?

Lambda runs on **Amazon Linux 2**, but we're developing on **macOS**. Packages with C extensions (psycopg2, pymupdf, Pillow) must be compiled for the target platform.

Docker lets us build in an Amazon Linux 2 environment that matches Lambda's runtime.

---

## Step 1: Install Docker Desktop

1. **Download Docker Desktop for macOS**:
   - Visit: https://www.docker.com/products/docker-desktop
   - Download the installer for Apple Silicon (M1/M2) or Intel

2. **Install Docker Desktop**:
   - Open the downloaded `.dmg` file
   - Drag Docker to Applications
   - Launch Docker Desktop from Applications

3. **Verify Installation**:
   ```bash
   docker --version
   # Should output: Docker version 24.x.x or similar
   ```

4. **Start Docker Desktop**:
   - Docker Desktop must be running (check menu bar for Docker icon)
   - Wait for "Docker Desktop is running" message

---

## Step 2: Verify Docker Works

Test Docker with a simple command:

```bash
docker run hello-world
```

You should see:
```
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

---

## Step 3: Test Lambda Layer Build

Once Docker is running, test the layer build:

```bash
cd terraform/modules/lambda-layer
./build_layer_docker.sh requirements.txt /tmp/test-layer
```

**Expected Output**:
- Docker builds Amazon Linux 2 image
- Packages are installed
- Layer ZIP is created
- JSON output for Terraform

**If successful**, you'll see:
```json
{"output_dir": "/tmp/test-layer", "site_packages": "/tmp/test-layer/python/lib/python3.11/site-packages"}
```

---

## Step 4: Use in Terraform

The Terraform module automatically uses Docker when you run:

```bash
cd terraform/environments/dev
terraform plan
terraform apply
```

The build happens automatically - no manual steps needed!

---

## Troubleshooting

### Docker Not Starting

**Symptoms**: Docker Desktop won't start or crashes

**Solutions**:
- Restart your Mac
- Check System Preferences → Security & Privacy → Allow Docker
- Update Docker Desktop to latest version
- Check Docker Desktop logs: `~/Library/Containers/com.docker.docker/Data/log/`

### Build Takes Too Long

**First build**: ~5-10 minutes (downloads base image, compiles packages)  
**Subsequent builds**: ~2-3 minutes (uses cached layers)

**To speed up**:
- Keep Docker Desktop running
- Don't clean Docker cache unnecessarily

### Out of Disk Space

**Error**: `no space left on device`

**Solution**:
- Docker needs ~2GB for build
- Clean up old Docker images: `docker system prune -a`
- Free up disk space on your Mac

### Permission Denied

**Error**: `permission denied while trying to connect to the Docker daemon`

**Solution**:
- Ensure Docker Desktop is running
- Add your user to docker group (usually automatic on macOS)
- Restart terminal after Docker installation

---

## What Gets Built

The Docker build creates a Lambda layer with:

- **psycopg2-binary** - Compiled for Amazon Linux 2
- **pymupdf** - MuPDF bindings compiled for Amazon Linux 2  
- **Pillow** - Image processing compiled for Amazon Linux 2
- **python-dateutil** - Pure Python (works anywhere)
- **boto3** - Already in Lambda runtime (included for completeness)

All C extensions are compiled correctly for Lambda's runtime environment.

---

## Next Steps

Once Docker is set up:

1. ✅ Docker installed and running
2. ✅ Test build works
3. ✅ Run `terraform apply` to create Lambda layer
4. ✅ Deploy Lambda functions with layer attached
5. ✅ Test Lambda functions can import psycopg2

---

**You're all set!** The Docker solution ensures all packages work correctly in Lambda. 🐳

