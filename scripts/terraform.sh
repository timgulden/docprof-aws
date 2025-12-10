#!/bin/bash
# Terraform wrapper script for DocProf AWS
# Automatically uses the docprof-dev AWS profile

set -e

# Set AWS profile
export AWS_PROFILE=docprof-dev

# Change to terraform directory
cd "$(dirname "$0")/../terraform/environments/dev"

# Run terraform with all passed arguments
terraform "$@"

