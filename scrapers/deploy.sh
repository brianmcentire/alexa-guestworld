#!/bin/bash
# Deploy the scraper Lambda package to AWS.
# Usage:
#   ./deploy.sh              # deploy to both Lambdas
#   ./deploy.sh challenge    # deploy to ChallengeRoutesCalendarScraper only
#   ./deploy.sh guestworld   # deploy to GuestWorldScraper only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ZIP_FILE="$SCRIPT_DIR/build/scraper-lambda.zip"

if [ ! -f "$ZIP_FILE" ]; then
    echo "No zip found. Running build.sh first..."
    bash "$SCRIPT_DIR/build.sh"
fi

TARGET="${1:-all}"

deploy_function() {
    local name="$1"
    echo "Deploying to $name..."
    aws lambda update-function-code \
        --function-name "$name" \
        --zip-file "fileb://$ZIP_FILE" \
        --output text --query 'FunctionName'
    echo "Done."
}

case "$TARGET" in
    challenge)
        deploy_function "ChallengeRoutesCalendarScraper"
        ;;
    guestworld)
        deploy_function "GuestWorldScraper"
        ;;
    all)
        deploy_function "ChallengeRoutesCalendarScraper"
        deploy_function "GuestWorldScraper"
        ;;
    *)
        echo "Unknown target: $TARGET"
        echo "Usage: $0 [challenge|guestworld|all]"
        exit 1
        ;;
esac
