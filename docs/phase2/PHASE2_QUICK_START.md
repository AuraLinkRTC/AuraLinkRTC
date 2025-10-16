# Phase 2 Quick Start Guide

## 🚀 Getting Started with Phase 2 Features

This guide will help you quickly set up and use the Phase 2 features of AuraLinkRTC.

---

## Prerequisites

- ✅ Phase 1 infrastructure running
- ✅ PostgreSQL/Supabase database configured
- ✅ Redis instance available
- ✅ LiveKit server deployed
- ✅ Supabase Storage bucket created

---

## 1. Database Setup

### Apply Phase 2 Migration

```bash
# Connect to your database
psql -U postgres -d auralink

# Apply migration
\i scripts/db/migrations/002_phase2_schema.sql

# Verify tables created
\dt

# Expected output:
#  calls
#  call_participants
#  files
#  shareable_links
#  quality_metrics
#  contacts
```

---

## 2. Install Dependencies

### Shared Libraries

```bash
cd shared/libs/go
go mod tidy
go mod download
```

### Dashboard Service

```bash
cd auralink-dashboard-service
go get github.com/gorilla/mux
go get github.com/prometheus/client_golang/prometheus
go get golang.org/x/crypto/bcrypt
go mod tidy
```

---

## 3. Environment Configuration

### Create .env file

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://livekit.yourdomain.com
LIVEKIT_API_KEY=your_api_key_here
LIVEKIT_API_SECRET=your_api_secret_here

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
SUPABASE_STORAGE_BUCKET=auralink-files

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/auralink

# Redis
REDIS_URL=redis://localhost:6379

# Service Configuration
SERVICE_PORT=8080
LOG_LEVEL=info
ENVIRONMENT=production
```

---

## 4. Configure LiveKit Webhooks

### In your LiveKit config.yaml:

```yaml
webhook:
  urls:
    - https://your-api-domain.com/webhooks/livekit
  api_key: your_webhook_secret_key
```

---

## 5. Create Storage Bucket

### In Supabase Dashboard:

1. Go to Storage
2. Create new bucket: `auralink-files`
3. Set bucket to Private
4. Configure CORS if needed

---

## 6. Test the APIs

### Create a Call

```bash
curl -X POST https://api.auralink.com/api/v1/rooms \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Meeting",
    "call_type": "group",
    "max_participants": 10,
    "screen_sharing_enabled": true,
    "file_sharing_enabled": true
  }'
```

### Join a Call

```bash
curl -X POST https://api.auralink.com/api/v1/rooms/{call_id}/token \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "John Doe"
  }'
```

### Upload a File

```bash
curl -X POST https://api.auralink.com/api/v1/files/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@/path/to/file.pdf" \
  -F "call_id=uuid" \
  -F "access_level=call_participants"
```

### Create Shareable Link

```bash
curl -X POST https://api.auralink.com/api/v1/links \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "uuid",
    "title": "Join Our Meeting",
    "access_type": "public",
    "expires_in_hours": 24
  }'
```

---

## 7. Monitor Quality Metrics

### Record Metrics (called by client SDK):

```bash
curl -X POST https://api.auralink.com/api/v1/quality/metrics \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "uuid",
    "participant_id": "uuid",
    "packet_loss_percent": 1.5,
    "latency_ms": 45,
    "quality_score": 4.2
  }'
```

### Get Quality Metrics:

```bash
curl -X GET "https://api.auralink.com/api/v1/quality/metrics?call_id=uuid" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## 8. Client SDK Integration Example

### JavaScript/TypeScript

```typescript
import { Room, RoomEvent, VideoPresets } from 'livekit-client';

// Get token from your backend
const response = await fetch('/api/v1/rooms/{callId}/token', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${jwt}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    display_name: 'User Name'
  })
});

const { token, room_name } = await response.json();

// Connect to room
const room = new Room({
  adaptiveStream: true,
  dynacast: true,
  videoCaptureDefaults: {
    resolution: VideoPresets.h720.resolution
  }
});

room.on(RoomEvent.Connected, () => {
  console.log('Connected to room');
});

room.on(RoomEvent.ParticipantConnected, (participant) => {
  console.log('Participant joined:', participant.identity);
});

await room.connect('wss://livekit.yourdomain.com', token);

// Enable camera and microphone
await room.localParticipant.setCameraEnabled(true);
await room.localParticipant.setMicrophoneEnabled(true);
```

---

## 9. File Sharing Integration

```typescript
// Upload file during call
async function uploadFile(file: File, callId: string) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('call_id', callId);
  formData.append('access_level', 'call_participants');
  
  const response = await fetch('/api/v1/files/upload', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwt}`
    },
    body: formData
  });
  
  return await response.json();
}

// List files in call
async function listFiles(callId: string) {
  const response = await fetch(`/api/v1/files?call_id=${callId}`, {
    headers: {
      'Authorization': `Bearer ${jwt}`
    }
  });
  
  const { files } = await response.json();
  return files;
}
```

---

## 10. Shareable Links Integration

```typescript
// Create shareable link
async function createShareableLink(callId: string) {
  const response = await fetch('/api/v1/links', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwt}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      call_id: callId,
      title: 'Join Our Meeting',
      access_type: 'public',
      expires_in_hours: 24,
      enable_recording: false,
      default_role: 'participant'
    })
  });
  
  const { url, short_code } = await response.json();
  return { url, short_code };
}

// Validate link (for join page)
async function validateLink(shortCode: string, password?: string) {
  const response = await fetch(`/api/v1/links/validate/${shortCode}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ password })
  });
  
  return await response.json();
}
```

---

## 11. Quality Monitoring Integration

```typescript
// Send quality metrics periodically
setInterval(async () => {
  const stats = await room.localParticipant.getStats();
  
  await fetch('/api/v1/quality/metrics', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwt}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      call_id: currentCallId,
      participant_id: participantId,
      packet_loss_percent: stats.packetLoss,
      latency_ms: stats.latency,
      bandwidth_kbps: stats.bandwidth,
      quality_score: calculateQuality(stats)
    })
  });
}, 10000); // Every 10 seconds
```

---

## 12. Troubleshooting

### Database Connection Issues

```bash
# Check database connection
psql -U postgres -d auralink -c "SELECT version();"

# Verify tables exist
psql -U postgres -d auralink -c "\dt"

# Check RLS policies
psql -U postgres -d auralink -c "SELECT * FROM pg_policies WHERE tablename = 'calls';"
```

### LiveKit Connection Issues

```bash
# Test LiveKit API
curl -X GET https://livekit.yourdomain.com/rooms \
  -H "Authorization: Bearer $(echo -n 'APIKey:APISecret' | base64)"

# Check webhooks are configured
curl -X GET https://your-api-domain.com/webhooks/livekit
```

### Storage Issues

```bash
# Verify Supabase Storage bucket
curl https://your-project.supabase.co/storage/v1/bucket/auralink-files \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY"
```

---

## 13. Common Errors

### "Room Full" Error
- Check `max_participants` setting
- Verify participant count in database
- Ensure cleanup of disconnected participants

### "Link Expired" Error
- Check `expires_at` timestamp
- Verify link `is_active` status
- Create new link if needed

### "Access Denied" Error
- Verify JWT token is valid
- Check user has permission to access resource
- Verify RLS policies are correctly configured

---

## 14. Performance Tips

### Database Optimization
- Ensure all indexes are created
- Run `ANALYZE` on tables periodically
- Monitor slow query log

### File Upload Optimization
- Use presigned URLs for direct client uploads
- Implement chunked uploads for large files
- Set appropriate `max_file_size` limits

### Quality Monitoring
- Send metrics every 10-30 seconds (not more frequently)
- Aggregate metrics on client before sending
- Use batch inserts if sending multiple metrics

---

## 15. Next Steps

- ✅ Implement client SDKs
- ✅ Add recording functionality
- ✅ Implement virus scanning for files
- ✅ Set up alerting for quality issues
- ✅ Configure CDN for file delivery
- 🚀 Move to Phase 3: AIC Protocol

---

## Support

- **Documentation**: `/docs/phase2/`
- **API Reference**: Generated from code
- **Issues**: GitHub Issues
- **Community**: Discord/Slack

---

*Generated: October 15, 2025*  
*© 2025 AuraLinkRTC Inc. All rights reserved.*
