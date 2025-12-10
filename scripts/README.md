# Scripts Directory

Utility scripts for deployment, testing, and maintenance.

## Planned Scripts

### Deployment
- `deploy_lambdas.sh` - Package and deploy all Lambda functions
- `deploy_frontend.sh` - Build and deploy React app to S3/CloudFront
- `deploy_all.sh` - Full stack deployment

### Testing
- `test_api.sh` - Integration tests for API Gateway endpoints
- `test_lambda.sh [function-name]` - Test individual Lambda function
- `benchmark_vector_search.py` - Performance testing

### Utilities
- `tail_logs.sh [function-name]` - Stream CloudWatch logs
- `estimate_costs.sh` - Calculate current monthly cost estimate
- `export_corpus.py` - Export corpus from MAExpert for migration
- `cleanup.sh` - Remove old logs, unused resources

### Monitoring
- `check_health.sh` - Health check for all services
- `analyze_costs.py` - Cost analysis and optimization suggestions

Scripts will be added as we progress through the migration phases.

