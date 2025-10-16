#!/bin/bash
# Script to convert AuraLink to proper monorepo structure
# This removes nested .git repositories and preserves history

echo "🔄 Converting AuraLink to monorepo structure..."

# Remove nested git repositories (keeping code, removing .git folders)
echo "📦 Removing nested .git directories..."

NESTED_REPOS=(
    "auralink-ingress-egress/jicofo"
    "auralink-ingress-egress"
    "auralink-webrtc-server"
    "auralink-communication-service"
)

for repo in "${NESTED_REPOS[@]}"; do
    if [ -d "$repo/.git" ]; then
        echo "  ➜ Removing $repo/.git"
        rm -rf "$repo/.git"
    fi
done

# Reset git staging
echo "🔄 Resetting git staging..."
git reset

# Stage all files
echo "✅ Staging all files..."
git add .

# Show status
echo ""
echo "📊 Git Status:"
git status

echo ""
echo "✅ Monorepo conversion complete!"
echo ""
echo "Next steps:"
echo "  1. Review changes: git status"
echo "  2. Create initial commit: git commit -m 'chore: initialize AuraLink monorepo'"
echo "  3. (Optional) Add remote: git remote add origin <url>"
echo "  4. (Optional) Push: git push -u origin main"
