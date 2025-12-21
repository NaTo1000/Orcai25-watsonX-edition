# Deployment Guide

## Prerequisites

- Python 3.8 or higher
- 2GB RAM minimum (4GB recommended)
- Network connectivity for threat intelligence feeds
- Secure key management system (HSM, AWS KMS, or HashiCorp Vault recommended)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/NaTo1000/Orcai25-watsonX-edition.git
cd Orcai25-watsonX-edition
```

### 2. Configuration

Edit `config/security_config.json` to match your environment:

```json
{
  "security": {
    "zero_trust": {
      "enabled": true,
      "mfa_required_for_high_trust": true,
      "session_timeout_seconds": 3600
    },
    "encryption": {
      "enabled": true,
      "quantum_resistant": true
    }
  },
  "emergency_protocols": {
    "emergency_contacts": [
      "your-security-team@example.com"
    ]
  }
}
```

### 3. Initialize Security Stack

```bash
python orcai_security.py
```

## Production Deployment

### Environment Setup

1. **Secure Key Management**
   - Use HSM or cloud KMS for secret keys
   - Rotate keys regularly
   - Never commit keys to source control

2. **Network Configuration**
   - Enable TLS 1.3 for all communications
   - Configure firewall rules
   - Set up network segmentation

3. **Monitoring Integration**
   - Connect to SIEM system
   - Configure alerting channels
   - Set up log aggregation

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run security stack
CMD ["python", "orcai_security.py"]
```

Build and run:

```bash
docker build -t orcai-security:latest .
docker run -d \
  -v /path/to/config:/app/config \
  -v /path/to/logs:/app/logs \
  --name orcai-security \
  orcai-security:latest
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orcai-security
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orcai-security
  template:
    metadata:
      labels:
        app: orcai-security
    spec:
      containers:
      - name: orcai-security
        image: orcai-security:latest
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: secrets
          mountPath: /app/secrets
          readOnly: true
      volumes:
      - name: config
        configMap:
          name: orcai-config
      - name: secrets
        secret:
          secretName: orcai-secrets
```

## Integration

### Integrating with Existing Systems

#### 1. Zero Trust Authentication

```python
from core.zero_trust_architecture import ZeroTrustEngine, SecurityContext, TrustLevel
import time

# Initialize
zero_trust = ZeroTrustEngine(secret_key="your-secret-key")

# In your authentication handler
def authenticate_request(request):
    context = SecurityContext(
        user_id=request.user_id,
        device_id=request.device_id,
        ip_address=request.ip_address,
        timestamp=time.time(),
        session_token=request.session_token,
        trust_level=TrustLevel.MEDIUM,
        mfa_verified=request.mfa_verified,
        behavioral_score=calculate_behavior_score(request)
    )
    
    status = zero_trust.verify_request(context)
    return status == VerificationStatus.VERIFIED
```

#### 2. AI System Monitoring

```python
from emergency_protocols.rogue_ai_containment import RogueAIDetector

# Initialize detector
detector = RogueAIDetector()

# Register your AI system
def shutdown_ai_system():
    # Your shutdown logic
    pass

detector.register_system("my_ai_system", shutdown_ai_system)

# Monitor behavior
def monitor_ai():
    metrics = {
        "goal_adherence_score": ai_system.get_goal_adherence(),
        "safety_check_bypasses": ai_system.get_safety_violations(),
        "resource_acquisition_rate": ai_system.get_resource_usage()
    }
    
    is_rogue = detector.check_for_rogue_behavior("my_ai_system", metrics)
    if is_rogue:
        # Handle emergency
        print(f"Emergency level: {detector.emergency_level}")
```

#### 3. Audit Logging

```python
from audit.compliance_framework import AuditLogger, AuditEventType

# Initialize logger
audit_logger = AuditLogger(secret_key="your-secret-key")

# Log events in your application
def handle_sensitive_operation(user, resource, action):
    # Perform operation
    result = perform_operation(user, resource, action)
    
    # Log to audit trail
    audit_logger.log_event(
        AuditEventType.ACCESS,
        actor=user.id,
        resource=resource.id,
        action=action,
        result="success" if result else "failure",
        details={"timestamp": time.time()}
    )
```

## Monitoring and Maintenance

### Health Checks

```bash
# Run health check
curl http://localhost:8080/health

# Expected response
{
  "status": "healthy",
  "components": {
    "zero_trust": "operational",
    "encryption": "operational",
    "monitoring": "operational"
  }
}
```

### Log Monitoring

Logs are output to stdout by default. In production:

1. **Centralized Logging**: Forward to ELK, Splunk, or CloudWatch
2. **Alert Configuration**: Set up alerts for critical events
3. **Log Rotation**: Implement log rotation policies

### Metrics Collection

Key metrics to monitor:

- Failed authentication attempts
- Emergency alert frequency
- Compliance check results
- System resource usage
- API error rates

## Troubleshooting

### Common Issues

#### 1. Configuration Not Loading

```bash
# Check config file exists
ls -la config/security_config.json

# Validate JSON
python -m json.tool config/security_config.json
```

#### 2. Import Errors

```bash
# Ensure all __init__.py files exist
find . -name "__init__.py"

# Check Python path
python -c "import sys; print(sys.path)"
```

#### 3. Memory Issues

Increase memory allocation:

```bash
# Docker
docker run -m 4g orcai-security:latest

# Kubernetes
resources:
  limits:
    memory: "4Gi"
```

## Security Hardening

### Production Security Checklist

- [ ] Secrets stored in secure key management system
- [ ] TLS 1.3 enabled for all communications
- [ ] Firewall rules configured
- [ ] Network segmentation implemented
- [ ] Monitoring integrated with SIEM
- [ ] Log aggregation configured
- [ ] Backup procedures tested
- [ ] Incident response plan documented
- [ ] Emergency contacts updated
- [ ] Compliance requirements verified

### Regular Maintenance

- **Daily**: Review security alerts
- **Weekly**: Compliance check, log analysis
- **Monthly**: Security patches, key rotation
- **Quarterly**: Full security audit, policy review
- **Annually**: Penetration testing, disaster recovery drill

## Scaling

### Horizontal Scaling

Deploy multiple instances behind load balancer:

```bash
# Scale with Kubernetes
kubectl scale deployment orcai-security --replicas=5

# Scale with Docker Swarm
docker service scale orcai-security=5
```

### Performance Optimization

1. **Caching**: Enable session caching
2. **Database**: Use connection pooling
3. **Async**: Leverage async operations
4. **Monitoring**: Use dedicated monitoring instances

## Backup and Recovery

### Backup Procedures

1. **Configuration**: Version control
2. **Audit Logs**: Daily backup to immutable storage
3. **Keys**: Secure backup with encryption
4. **State**: Regular snapshots

### Recovery Procedures

1. Stop affected systems
2. Restore from latest backup
3. Verify integrity
4. Resume operations
5. Document incident

## Support

For deployment assistance:
- Documentation: See `/docs` directory
- Issues: GitHub Issues
- Security: security@orcai25.example.com
- Emergency: Use emergency contacts in config
