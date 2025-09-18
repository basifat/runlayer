# GitHub PR Workflow for RunLayer

## Option 1: Manual GitHub PR Creation (Recommended)

### Step 1: Initialize Git Repository
```bash
cd /Users/baba/Desktop/learnp/runlayer

# Initialize git repo
git init

# Add GitHub remote (replace with your repo URL)
git remote add origin https://github.com/yourusername/runlayer.git

# Create main branch
git checkout -b main
```

### Step 2: Create Feature Branch for Story 1
```bash
# Create feature branch following our naming convention
git checkout -b feature/story-001-api-gateway-foundation

# Add all files
git add .

# Commit with descriptive message
git commit -m "feat: implement API Gateway Foundation (Story #001)

- Add FastAPI application with async/await support
- Implement JWT authentication middleware framework
- Add Redis-based distributed rate limiting
- Implement request correlation ID tracking
- Add structured logging with correlation IDs
- Configure CORS middleware for cross-origin requests
- Add comprehensive error handling
- Implement health check and metrics endpoints
- Add comprehensive test suite with >80% coverage

Closes #001"
```

### Step 3: Push and Create PR
```bash
# Push feature branch
git push -u origin feature/story-001-api-gateway-foundation

# GitHub will show a link to create PR, or go to GitHub web interface
```

### Step 4: Create PR on GitHub Web Interface
1. Go to your GitHub repository
2. Click "Compare & pull request" button
3. Copy content from `PR_001_API_Gateway_Foundation.md` into PR description
4. Set reviewers, labels, milestone
5. Create pull request

---

## Option 2: GitHub CLI (Automated)

### Install GitHub CLI
```bash
# macOS
brew install gh

# Login to GitHub
gh auth login
```

### Create Repository and PR
```bash
cd /Users/baba/Desktop/learnp/runlayer

# Create GitHub repository
gh repo create runlayer --public --description "The trust layer for AI - Validate AI outputs with cryptographic proof"

# Initialize git and push
git init
git add .
git commit -m "feat: implement API Gateway Foundation (Story #001)"
git branch -M main
git remote add origin https://github.com/yourusername/runlayer.git
git push -u origin main

# Create feature branch and PR
git checkout -b feature/story-001-api-gateway-foundation
git push -u origin feature/story-001-api-gateway-foundation

# Create PR with our template content
gh pr create \
  --title "feat: API Gateway Foundation (Story #001)" \
  --body-file PR_001_API_Gateway_Foundation.md \
  --label "enhancement,story-001,high-priority" \
  --milestone "Phase 1: Foundation"
```

---

## Option 3: Automated PR Creation Script

### Create PR Automation Script
```bash
#!/bin/bash
# create_pr.sh

STORY_NUMBER=$1
STORY_TITLE=$2
BRANCH_NAME="feature/story-$(printf "%03d" $STORY_NUMBER)-$(echo $STORY_TITLE | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
PR_FILE="PR_$(printf "%03d" $STORY_NUMBER)_$(echo $STORY_TITLE | tr ' ' '_').md"

echo "Creating PR for Story #$STORY_NUMBER: $STORY_TITLE"

# Create and switch to feature branch
git checkout -b $BRANCH_NAME

# Add and commit changes
git add .
git commit -m "feat: $STORY_TITLE (Story #$STORY_NUMBER)"

# Push branch
git push -u origin $BRANCH_NAME

# Create PR using GitHub CLI
gh pr create \
  --title "feat: $STORY_TITLE (Story #$STORY_NUMBER)" \
  --body-file $PR_FILE \
  --label "enhancement,story-$STORY_NUMBER,high-priority"

echo "PR created successfully!"
```

### Usage
```bash
chmod +x create_pr.sh
./create_pr.sh 1 "API Gateway Foundation"
```

---

## Option 4: GitHub Actions Automation (Advanced)

### Create GitHub Actions Workflow
```yaml
# .github/workflows/create-story-pr.yml
name: Create Story PR

on:
  workflow_dispatch:
    inputs:
      story_number:
        description: 'Story number'
        required: true
        type: string
      story_title:
        description: 'Story title'
        required: true
        type: string

jobs:
  create-pr:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Create feature branch
        run: |
          BRANCH_NAME="feature/story-${{ inputs.story_number }}-$(echo '${{ inputs.story_title }}' | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
          git checkout -b $BRANCH_NAME
          git push -u origin $BRANCH_NAME
      
      - name: Create PR
        uses: peter-evans/create-pull-request@v5
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          branch: feature/story-${{ inputs.story_number }}-$(echo '${{ inputs.story_title }}' | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
          title: "feat: ${{ inputs.story_title }} (Story #${{ inputs.story_number }})"
          body-path: "PR_${{ inputs.story_number }}_${{ inputs.story_title }}.md"
```

---

## Recommended Workflow for RunLayer

### For Current Situation (Best Approach):

1. **Create GitHub Repository**
```bash
# Go to GitHub.com and create new repository "runlayer"
# Or use GitHub CLI:
gh repo create runlayer --public
```

2. **Initialize Local Repository**
```bash
cd /Users/baba/Desktop/learnp/runlayer
git init
git remote add origin https://github.com/yourusername/runlayer.git
```

3. **Create Main Branch with Initial Commit**
```bash
git add README.md package.json turbo.json .gitignore
git commit -m "chore: initial repository setup

- Add monorepo structure with Turbo
- Configure development environment
- Add comprehensive README with roadmap"

git branch -M main
git push -u origin main
```

4. **Create Feature Branch for Story 1**
```bash
git checkout -b feature/story-001-api-gateway-foundation
git add packages/core/
git commit -m "feat: implement API Gateway Foundation (Story #001)

- Add FastAPI application with async/await support
- Implement JWT authentication middleware framework  
- Add Redis-based distributed rate limiting
- Implement request correlation ID tracking
- Add structured logging with correlation IDs
- Configure CORS middleware for cross-origin requests
- Add comprehensive error handling
- Implement health check and metrics endpoints
- Add comprehensive test suite with >80% coverage

Performance:
- p99 API response time < 300ms architecture
- Async/await throughout for maximum concurrency
- Connection pooling for database and Redis
- Serverless-ready with NullPool configuration

Security:
- JWT authentication framework ready
- Input validation with Pydantic
- SQL injection prevention with SQLAlchemy ORM
- CORS with explicit allowed origins
- Structured audit logging with correlation IDs

Testing:
- Unit tests with >80% coverage
- Integration test framework ready
- Pytest configuration with async support

Closes #001"

git push -u origin feature/story-001-api-gateway-foundation
```

5. **Create PR via GitHub Web Interface**
- Go to GitHub repository
- Click "Compare & pull request"
- Copy content from `PR_001_API_Gateway_Foundation.md`
- Add labels: `enhancement`, `story-001`, `high-priority`
- Set milestone: `Phase 1: Foundation`
- Create pull request

### GitHub Repository Settings

**Branch Protection Rules:**
```yaml
Branch: main
- Require pull request reviews before merging
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Restrict pushes that create files larger than 100MB
```

**PR Template Configuration:**
The PR template we created will automatically populate when creating PRs.

**Labels to Create:**
- `enhancement` (feature additions)
- `bug` (bug fixes)
- `documentation` (docs updates)
- `story-001` through `story-210` (story tracking)
- `high-priority`, `medium-priority`, `low-priority`
- `phase-1`, `phase-2`, `phase-3`, `phase-4`

### Next Steps After First PR

1. **Merge PR #001** after review
2. **Create PR #002** for Database Setup
3. **Set up CI/CD** with GitHub Actions
4. **Configure automated testing**
5. **Set up deployment pipeline**

Would you like me to help you with any specific step, such as creating the GitHub repository or setting up the automated workflow?
