#!/bin/bash
# Invoke a scraper Lambda function.
# Usage:
#   ./trigger.sh              # invoke both scrapers
#   ./trigger.sh challenge    # invoke ChallengeRoutesCalendarScraper only
#   ./trigger.sh guestworld   # invoke GuestWorldScraper only

set -euo pipefail

TARGET="${1:-all}"

invoke_function() {
    local name="$1"
    echo "Invoking $name..."
    aws lambda invoke --function-name "$name" /dev/stdout
    echo ""
}

case "$TARGET" in
    challenge)
        invoke_function "ChallengeRoutesCalendarScraper"
        ;;
    guestworld)
        invoke_function "GuestWorldScraper"
        ;;
    all)
        invoke_function "ChallengeRoutesCalendarScraper"
        invoke_function "GuestWorldScraper"
        ;;
    *)
        echo "Unknown target: $TARGET"
        echo "Usage: $0 [challenge|guestworld|all]"
        exit 1
        ;;
esac
