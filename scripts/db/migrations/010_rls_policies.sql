-- Migration 010: Row-Level Security Policies
-- Description: Implements privacy controls for AuraID discovery and data access
-- Author: AuraLink Team
-- Date: 2025-10-16

-- ==============================================================================
-- ENABLE ROW LEVEL SECURITY
-- ==============================================================================

-- Enable RLS on aura_id_registry
ALTER TABLE aura_id_registry ENABLE ROW LEVEL SECURITY;

-- Enable RLS on aura_id_verifications
ALTER TABLE aura_id_verifications ENABLE ROW LEVEL SECURITY;

-- Enable RLS on matrix_user_mappings
ALTER TABLE matrix_user_mappings ENABLE ROW LEVEL SECURITY;

-- Enable RLS on cross_app_calls
ALTER TABLE cross_app_calls ENABLE ROW LEVEL SECURITY;

-- Enable RLS on notification_queue
ALTER TABLE notification_queue ENABLE ROW LEVEL SECURITY;

-- Enable RLS on device_registry
ALTER TABLE device_registry ENABLE ROW LEVEL SECURITY;

-- ==============================================================================
-- AURA_ID_REGISTRY POLICIES
-- ==============================================================================

-- Policy: Users can view their own AuraID
CREATE POLICY "users_view_own_auraid"
ON aura_id_registry
FOR SELECT
USING (user_id = auth.uid());

-- Policy: Users can view public AuraIDs
CREATE POLICY "view_public_auroids"
ON aura_id_registry
FOR SELECT
USING (privacy_level = 'public' AND is_active = true);

-- Policy: Users can view friends-only AuraIDs if they're mutual contacts
CREATE POLICY "view_friends_auroids"
ON aura_id_registry
FOR SELECT
USING (
    privacy_level = 'friends' 
    AND is_active = true
    AND EXISTS (
        SELECT 1 FROM contacts
        WHERE (
            (contacts.user_id = aura_id_registry.user_id 
             AND contacts.contact_user_id = auth.uid())
            OR
            (contacts.user_id = auth.uid() 
             AND contacts.contact_user_id = aura_id_registry.user_id)
        )
        AND contacts.status = 'accepted'
    )
);

-- Policy: Users can update their own AuraID settings
CREATE POLICY "users_update_own_auraid"
ON aura_id_registry
FOR UPDATE
USING (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());

-- Policy: Service role has full access
CREATE POLICY "service_role_full_access_auraid"
ON aura_id_registry
FOR ALL
USING (auth.role() = 'service_role');

-- ==============================================================================
-- AURA_ID_VERIFICATIONS POLICIES
-- ==============================================================================

-- Policy: Users can view their own verifications
CREATE POLICY "users_view_own_verifications"
ON aura_id_verifications
FOR SELECT
USING (
    registry_id IN (
        SELECT registry_id FROM aura_id_registry WHERE user_id = auth.uid()
    )
);

-- Policy: Users can insert their own verifications
CREATE POLICY "users_insert_own_verifications"
ON aura_id_verifications
FOR INSERT
WITH CHECK (
    registry_id IN (
        SELECT registry_id FROM aura_id_registry WHERE user_id = auth.uid()
    )
);

-- Policy: Users can update their own verifications
CREATE POLICY "users_update_own_verifications"
ON aura_id_verifications
FOR UPDATE
USING (
    registry_id IN (
        SELECT registry_id FROM aura_id_registry WHERE user_id = auth.uid()
    )
)
WITH CHECK (
    registry_id IN (
        SELECT registry_id FROM aura_id_registry WHERE user_id = auth.uid()
    )
);

-- Policy: Service role has full access
CREATE POLICY "service_role_full_access_verifications"
ON aura_id_verifications
FOR ALL
USING (auth.role() = 'service_role');

-- ==============================================================================
-- MATRIX_USER_MAPPINGS POLICIES
-- ==============================================================================

-- Policy: Users can view their own Matrix mapping
CREATE POLICY "users_view_own_matrix_mapping"
ON matrix_user_mappings
FOR SELECT
USING (
    registry_id IN (
        SELECT registry_id FROM aura_id_registry WHERE user_id = auth.uid()
    )
);

-- Policy: Users can view Matrix mappings for discoverable AuraIDs
CREATE POLICY "view_discoverable_matrix_mappings"
ON matrix_user_mappings
FOR SELECT
USING (
    aura_id IN (
        SELECT aura_id FROM aura_id_registry 
        WHERE is_active = true 
        AND (
            privacy_level = 'public'
            OR
            (privacy_level = 'friends' AND EXISTS (
                SELECT 1 FROM contacts
                WHERE (
                    (contacts.user_id = aura_id_registry.user_id 
                     AND contacts.contact_user_id = auth.uid())
                    OR
                    (contacts.user_id = auth.uid() 
                     AND contacts.contact_user_id = aura_id_registry.user_id)
                )
                AND contacts.status = 'accepted'
            ))
        )
    )
);

-- Policy: Service role has full access
CREATE POLICY "service_role_full_access_matrix_mappings"
ON matrix_user_mappings
FOR ALL
USING (auth.role() = 'service_role');

-- ==============================================================================
-- CROSS_APP_CALLS POLICIES
-- ==============================================================================

-- Policy: Users can view calls they participated in
CREATE POLICY "users_view_own_calls"
ON cross_app_calls
FOR SELECT
USING (
    caller_aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
    OR
    callee_aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
);

-- Policy: Users can insert calls they initiate
CREATE POLICY "users_insert_own_calls"
ON cross_app_calls
FOR INSERT
WITH CHECK (
    caller_aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
);

-- Policy: Users can update calls they participate in
CREATE POLICY "users_update_own_calls"
ON cross_app_calls
FOR UPDATE
USING (
    caller_aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
    OR
    callee_aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
)
WITH CHECK (
    caller_aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
    OR
    callee_aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
);

-- Policy: Service role has full access
CREATE POLICY "service_role_full_access_calls"
ON cross_app_calls
FOR ALL
USING (auth.role() = 'service_role');

-- ==============================================================================
-- NOTIFICATION_QUEUE POLICIES
-- ==============================================================================

-- Policy: Users can view their own notifications
CREATE POLICY "users_view_own_notifications"
ON notification_queue
FOR SELECT
USING (
    recipient_aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
);

-- Policy: Users can update their own notifications (mark as read/acted)
CREATE POLICY "users_update_own_notifications"
ON notification_queue
FOR UPDATE
USING (
    recipient_aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
)
WITH CHECK (
    recipient_aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
);

-- Policy: Service role has full access
CREATE POLICY "service_role_full_access_notifications"
ON notification_queue
FOR ALL
USING (auth.role() = 'service_role');

-- ==============================================================================
-- DEVICE_REGISTRY POLICIES
-- ==============================================================================

-- Policy: Users can view their own devices
CREATE POLICY "users_view_own_devices"
ON device_registry
FOR SELECT
USING (
    aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
);

-- Policy: Users can insert their own devices
CREATE POLICY "users_insert_own_devices"
ON device_registry
FOR INSERT
WITH CHECK (
    aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
);

-- Policy: Users can update their own devices
CREATE POLICY "users_update_own_devices"
ON device_registry
FOR UPDATE
USING (
    aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
)
WITH CHECK (
    aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
);

-- Policy: Users can delete their own devices
CREATE POLICY "users_delete_own_devices"
ON device_registry
FOR DELETE
USING (
    aura_id IN (SELECT aura_id FROM aura_id_registry WHERE user_id = auth.uid())
);

-- Policy: Service role has full access
CREATE POLICY "service_role_full_access_devices"
ON device_registry
FOR ALL
USING (auth.role() = 'service_role');

-- ==============================================================================
-- HELPER FUNCTION FOR SETTING CURRENT USER CONTEXT
-- ==============================================================================

-- Function to set current AuraID in session for RLS context
CREATE OR REPLACE FUNCTION set_current_auraid(p_aura_id VARCHAR(255))
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    PERFORM set_config('app.current_aura_id', p_aura_id, false);
END;
$$;

COMMENT ON FUNCTION set_current_auraid IS 'Sets current AuraID in session for RLS context';

-- Function to get current AuraID from session
CREATE OR REPLACE FUNCTION get_current_auraid()
RETURNS VARCHAR(255)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN current_setting('app.current_aura_id', true);
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$;

COMMENT ON FUNCTION get_current_auraid IS 'Gets current AuraID from session context';

-- ==============================================================================
-- GRANTS FOR RLS HELPER FUNCTIONS
-- ==============================================================================

GRANT EXECUTE ON FUNCTION set_current_auraid TO authenticated;
GRANT EXECUTE ON FUNCTION set_current_auraid TO service_role;
GRANT EXECUTE ON FUNCTION get_current_auraid TO authenticated;
GRANT EXECUTE ON FUNCTION get_current_auraid TO service_role;

-- ==============================================================================
-- VALIDATION COMMENTS
-- ==============================================================================

-- Privacy Level Enforcement:
-- - Public: Anyone can discover and call
-- - Friends: Only mutual contacts can discover
-- - Private: Only owner can see, not discoverable

-- RLS Policies ensure:
-- 1. Users can only access their own data
-- 2. Public AuraIDs are visible to all
-- 3. Friends-only AuraIDs visible to mutual contacts
-- 4. Private AuraIDs visible only to owner
-- 5. Service role bypasses RLS for system operations
-- 6. Cross-app calls visible to both participants
-- 7. Notifications visible only to recipient

-- Migration complete
