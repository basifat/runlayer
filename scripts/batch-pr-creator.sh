#!/bin/bash
# Batch PR Creator for RunLayer Stories
# Usage: ./batch-pr-creator.sh [phase_name] [--auto-commit]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [PHASE_NAME|STORY_IDS...]"
    echo ""
    echo "Options:"
    echo "  --auto-commit    Automatically commit changes (use with caution)"
    echo "  --dry-run        Show what would be done without executing"
    echo "  --help           Show this help message"
    echo ""
    echo "Phase Names:"
    echo "  phase_1_foundation    Stories: 001, 002, 002A, 002B, 002C, 016A"
    echo "  phase_2_sdk          Stories: 056, 057, 058, 059, 060"
    echo "  phase_2_marketplace  Stories: 066, 067, 068, 069, 070"
    echo ""
    echo "Examples:"
    echo "  $0 phase_1_foundation"
    echo "  $0 001 002 002A --auto-commit"
    echo "  $0 --dry-run phase_2_sdk"
}

# Parse command line arguments
AUTO_COMMIT=false
DRY_RUN=false
PHASE_NAME=""
STORY_IDS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --auto-commit)
            AUTO_COMMIT=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        phase_*)
            PHASE_NAME="$1"
            shift
            ;;
        [0-9]*)
            STORY_IDS+=("$1")
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Function to get story IDs from phase name
get_stories_from_phase() {
    local phase="$1"
    case $phase in
        phase_1_foundation)
            echo "001 002 002A 002B 002C 016A"
            ;;
        phase_2_sdk)
            echo "056 057 058 059 060"
            ;;
        phase_2_marketplace)
            echo "066 067 068 069 070"
            ;;
        *)
            print_error "Unknown phase: $phase"
            exit 1
            ;;
    esac
}

# Determine which stories to process
if [[ -n "$PHASE_NAME" ]]; then
    STORY_LIST=$(get_stories_from_phase "$PHASE_NAME")
    read -ra STORY_IDS <<< "$STORY_LIST"
    print_status "Processing phase: $PHASE_NAME"
    print_status "Stories: ${STORY_IDS[*]}"
elif [[ ${#STORY_IDS[@]} -eq 0 ]]; then
    print_error "No stories specified. Use a phase name or provide story IDs."
    show_usage
    exit 1
fi

# Validate prerequisites
print_status "Checking prerequisites..."

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository"
    exit 1
fi

# Check if GitHub CLI is installed and authenticated
if ! command -v gh &> /dev/null; then
    print_error "GitHub CLI (gh) is not installed"
    exit 1
fi

if ! gh auth status &> /dev/null; then
    print_error "GitHub CLI is not authenticated. Run: gh auth login"
    exit 1
fi

# Check if Python script exists
if [[ ! -f "$SCRIPT_DIR/auto-pr-generator.py" ]]; then
    print_error "auto-pr-generator.py not found in $SCRIPT_DIR"
    exit 1
fi

# Check if stories config exists
if [[ ! -f "$REPO_ROOT/stories-config.yml" ]]; then
    print_error "stories-config.yml not found in $REPO_ROOT"
    exit 1
fi

print_success "Prerequisites check passed"

# Function to create PR for a single story
create_story_pr() {
    local story_id="$1"
    local auto_commit_flag=""
    
    if [[ "$AUTO_COMMIT" == "true" ]]; then
        auto_commit_flag="--auto-commit"
    fi
    
    print_status "Creating PR for Story #$story_id..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        print_warning "DRY RUN: Would create PR for Story #$story_id"
        return 0
    fi
    
    if python3 "$SCRIPT_DIR/auto-pr-generator.py" "$story_id" $auto_commit_flag; then
        print_success "PR created for Story #$story_id"
        return 0
    else
        print_error "Failed to create PR for Story #$story_id"
        return 1
    fi
}

# Main execution
print_status "Starting batch PR creation..."
print_status "Stories to process: ${STORY_IDS[*]}"
print_status "Auto-commit: $AUTO_COMMIT"
print_status "Dry run: $DRY_RUN"

if [[ "$DRY_RUN" == "false" ]]; then
    echo ""
    read -p "Continue with PR creation? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Aborted by user"
        exit 0
    fi
fi

# Track results
SUCCESSFUL_PRS=()
FAILED_PRS=()

# Process each story
for story_id in "${STORY_IDS[@]}"; do
    if create_story_pr "$story_id"; then
        SUCCESSFUL_PRS+=("$story_id")
    else
        FAILED_PRS+=("$story_id")
    fi
    
    # Add delay between PRs to avoid rate limiting
    if [[ "$DRY_RUN" == "false" ]]; then
        sleep 2
    fi
done

# Summary
echo ""
print_status "=== BATCH PR CREATION SUMMARY ==="
print_success "Successful PRs: ${#SUCCESSFUL_PRS[@]}"
for story_id in "${SUCCESSFUL_PRS[@]}"; do
    echo "  ✅ Story #$story_id"
done

if [[ ${#FAILED_PRS[@]} -gt 0 ]]; then
    print_error "Failed PRs: ${#FAILED_PRS[@]}"
    for story_id in "${FAILED_PRS[@]}"; do
        echo "  ❌ Story #$story_id"
    done
fi

# Exit with appropriate code
if [[ ${#FAILED_PRS[@]} -eq 0 ]]; then
    print_success "All PRs created successfully! 🎉"
    exit 0
else
    print_error "Some PRs failed to create"
    exit 1
fi
