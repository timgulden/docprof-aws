# AI Services UI Integration Guide

**Status**: Ready for implementation  
**Date**: 2025-01-XX

## Overview

This guide explains how to integrate the "Enable AI Services" switch into the frontend UI, replacing the current "External Internet Access" (Cloudflare Tunnel) switch.

## Architecture

```
Frontend UI Switch
    ↓
API Gateway
    ├─ GET /ai-services/status → Check current status
    ├─ POST /ai-services/enable → Enable VPC endpoints
    └─ POST /ai-services/disable → Disable VPC endpoints
    ↓
AI Services Manager Lambda
    ├─ Check VPC endpoint status (EC2 API)
    ├─ Create VPC endpoints (Bedrock + Polly)
    └─ Delete VPC endpoints
```

## API Endpoints

### 1. Check Status

**GET** `/ai-services/status`

**Response**:
```json
{
  "enabled": true,
  "status": "online",  // "online" | "offline" | "working"
  "bedrock": {
    "endpoint_id": "vpce-xxx",
    "status": "online"
  },
  "polly": {
    "endpoint_id": "vpce-yyy",
    "status": "online"
  },
  "message": "AI services are online and ready to use"
}
```

### 2. Enable Services

**POST** `/ai-services/enable`

**Response**:
```json
{
  "enabled": true,
  "status": "working",  // Will be "working" initially, then "online" when ready
  "bedrock": {
    "endpoint_id": "vpce-xxx",
    "status": "working"
  },
  "polly": {
    "endpoint_id": "vpce-yyy",
    "status": "working"
  },
  "message": "AI services are being enabled. This may take 3-5 minutes."
}
```

### 3. Disable Services

**POST** `/ai-services/disable`

**Response**:
```json
{
  "enabled": false,
  "status": "offline",
  "deleted": ["bedrock", "polly"],
  "message": "AI services are being disabled. This may take a few minutes."
}
```

## Frontend Integration

### 1. Create API Functions

**File**: `src/api/aiServices.ts` (or similar)

```typescript
const API_BASE_URL = process.env.REACT_APP_API_URL || '';

export interface AIServicesStatus {
  enabled: boolean;
  status: 'online' | 'offline' | 'working';
  bedrock: {
    endpoint_id: string | null;
    status: string;
  };
  polly: {
    endpoint_id: string | null;
    status: string;
  };
  message: string;
}

export async function getAIServicesStatus(): Promise<AIServicesStatus> {
  const response = await fetch(`${API_BASE_URL}/ai-services/status`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get AI services status: ${response.statusText}`);
  }

  return response.json();
}

export async function enableAIServices(): Promise<AIServicesStatus> {
  const response = await fetch(`${API_BASE_URL}/ai-services/enable`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to enable AI services: ${response.statusText}`);
  }

  return response.json();
}

export async function disableAIServices(): Promise<AIServicesStatus> {
  const response = await fetch(`${API_BASE_URL}/ai-services/disable`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to disable AI services: ${response.statusText}`);
  }

  return response.json();
}
```

### 2. Update Layout Component

**File**: `src/components/common/Layout.tsx`

Replace the tunnel switch with AI services switch:

```typescript
import { getAIServicesStatus, enableAIServices, disableAIServices } from "../../api/aiServices";

// In component:
const { data: aiStatus, isLoading: aiLoading } = useQuery({
  queryKey: ["ai-services-status"],
  queryFn: getAIServicesStatus,
  refetchInterval: (data) => {
    // Poll every 5 seconds if status is "working", otherwise every 30 seconds
    return data?.status === 'working' ? 5000 : 30000;
  },
  retry: false,
});

const enableMutation = useMutation({
  mutationFn: enableAIServices,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["ai-services-status"] });
  },
});

const disableMutation = useMutation({
  mutationFn: disableAIServices,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["ai-services-status"] });
  },
});

const handleAIServicesToggle = () => {
  if (aiStatus?.enabled) {
    disableMutation.mutate();
  } else {
    enableMutation.mutate();
  }
};

// In JSX (replace tunnel switch):
{isSourcesRoute && aiStatus !== undefined && (
  <>
    <div className="w-12"></div>
    <div className="flex flex-col items-start">
      <div className="flex items-center gap-2">
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={aiStatus.enabled}
            onChange={handleAIServicesToggle}
            disabled={aiLoading || enableMutation.isPending || disableMutation.isPending}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          <span className="ml-3 text-sm font-medium text-gray-700">
            {aiStatus.status === 'working' ? 'Working...' : aiStatus.enabled ? 'AI Services: ON' : 'AI Services: OFF'}
          </span>
        </label>
      </div>
      {aiStatus.message && (
        <p className="text-xs text-gray-500 mt-1">{aiStatus.message}</p>
      )}
    </div>
  </>
)}
```

### 3. Status Indicators

**Visual States**:

- **OFF (offline)**: Switch off, gray, "AI Services: OFF"
- **WORKING**: Switch on, yellow/orange, "Working...", polling every 5 seconds
- **ON (online)**: Switch on, green, "AI Services: ON", polling every 30 seconds

**Status Messages**:
- `"AI services are online and ready to use"`
- `"AI services are offline. Enable to use AI features."`
- `"AI services are being configured. Please wait..."`

## User Experience Flow

1. **User visits Sources page**
   - Switch shows current status (fetched on page load)
   - Status polls automatically (every 30 seconds when stable)

2. **User toggles switch ON**
   - Switch immediately shows "Working..."
   - API call to enable services
   - Status polls every 5 seconds until "online"
   - Switch shows "AI Services: ON" when ready

3. **User toggles switch OFF**
   - Switch immediately shows "Working..."
   - API call to disable services
   - Status polls every 5 seconds until "offline"
   - Switch shows "AI Services: OFF" when done

## Error Handling

```typescript
const { data: aiStatus, error, isLoading } = useQuery({
  queryKey: ["ai-services-status"],
  queryFn: getAIServicesStatus,
  refetchInterval: 30000,
  retry: false,
  onError: (error) => {
    console.error("Failed to fetch AI services status:", error);
    // Show error toast or message
  },
});

// In mutations:
const enableMutation = useMutation({
  mutationFn: enableAIServices,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["ai-services-status"] });
    // Show success toast
  },
  onError: (error) => {
    console.error("Failed to enable AI services:", error);
    // Show error toast
  },
});
```

## Security Considerations

⚠️ **Current Implementation**: No authentication (open to public)

🔒 **Production Recommendations**:
- Add Cognito authentication to API Gateway endpoints
- Restrict access to admin users only (e.g., user "tim")
- Add rate limiting to prevent abuse
- Consider adding confirmation dialog before enabling (costs money)

## Cost Information

**When Enabled**:
- ~$0.04/hour (~$0.96/day if running 24/7)
- Bedrock endpoint: ~$0.01/hour per AZ
- Polly endpoint: ~$0.01/hour per AZ
- 2 AZs × 2 endpoints = ~$0.04/hour

**When Disabled**:
- $0/hour (no charges)

**Recommendation**: Show cost estimate in UI when enabling:
```
"Enabling AI services will cost approximately $0.04/hour (~$1/day if running continuously)."
```

## Testing

### Manual Testing

1. **Check Status**:
   ```bash
   curl https://{api-id}.execute-api.{region}.amazonaws.com/dev/ai-services/status
   ```

2. **Enable Services**:
   ```bash
   curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/dev/ai-services/enable
   ```

3. **Disable Services**:
   ```bash
   curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/dev/ai-services/disable
   ```

### Integration Testing

1. Deploy infrastructure
2. Open Sources page in frontend
3. Toggle switch ON → Verify status changes to "working" then "online"
4. Toggle switch OFF → Verify status changes to "working" then "offline"
5. Verify VPC endpoints are created/deleted in AWS Console

## Migration from Tunnel Switch

**Steps**:
1. Keep tunnel switch code commented out (for reference)
2. Add AI services API functions
3. Replace tunnel switch with AI services switch
4. Test thoroughly
5. Remove tunnel switch code once confirmed working

**Key Differences**:
- Tunnel: Controls Cloudflare Tunnel (external access)
- AI Services: Controls VPC endpoints (Bedrock/Polly access)
- Both: Only visible to admin user ("tim")
- Both: Show status with polling

## Next Steps

1. ✅ Lambda function created
2. ✅ API Gateway endpoints configured
3. ⏳ Frontend integration (replace tunnel switch)
4. ⏳ Deploy and test
5. ⏳ Add authentication (production)

