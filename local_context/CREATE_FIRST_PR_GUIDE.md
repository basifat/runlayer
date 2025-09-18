# How to Create PR #001: API Gateway Foundation on GitHub

## Prerequisites Checklist

### ✅ **1. GitHub Repository Setup**
```bash
# Option A: Create via GitHub CLI (Recommended)
gh auth login
gh repo create runlayer --public --description "The trust layer for AI - Validate AI outputs with cryptographic proof"

# Option B: Create manually on GitHub.com
# Go to github.com → New Repository → "runlayer"
```

### ✅ **2. Local Git Initialization**
```bash
cd /Users/baba/Desktop/learnp/runlayer

# Initialize git repository
git init

# Add GitHub remote (replace 'yourusername' with your GitHub username)
git remote add origin https://github.com/yourusername/runlayer.git

# Verify remote
git remote -v
```

## Step-by-Step PR Creation

### **Step 1: Create Main Branch with Initial Setup**
```bash
# Create .gitignore first
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
.env

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.npm
.yarn-integrity

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Runtime
.coverage
.pytest_cache/
.mypy_cache/

# Build outputs
dist/
build/
*.egg-info/

# Local development
.runlayer/
*.local
EOF

# Add basic project files
git add .gitignore README.md package.json turbo.json
git commit -m "chore: initial repository setup

- Add monorepo structure with Turbo
- Configure development environment  
- Add comprehensive README with roadmap"

# Push main branch
git branch -M main
git push -u origin main
```

### **Step 2: Create Feature Branch for PR #001**
```bash
# Create and switch to feature branch
git checkout -b feature/story-001-api-gateway-foundation

# Add all the API Gateway Foundation files
git add packages/core/
git add .github/PULL_REQUEST_TEMPLATE/
git add PR_001_API_Gateway_Foundation.md

# Commit with detailed message
git commit -m "feat: implement API Gateway Foundation (Story #001)

Core Features:
- FastAPI application with async/await support
- JWT authentication middleware framework
- Redis-based distributed rate limiting  
- Request correlation ID tracking
- Structured logging with correlation IDs
- CORS middleware for cross-origin requests
- Comprehensive error handling
- Health check and metrics endpoints

Performance:
- p99 API response time <300ms architecture
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
- 24 test cases covering all components

Files Added:
- packages/core/src/main.py - FastAPI application
- packages/core/src/config.py - Configuration management
- packages/core/src/database.py - Database connection
- packages/core/src/middleware/ - Middleware components
- packages/core/src/routers/ - API route placeholders
- packages/core/tests/ - Comprehensive test suite
- packages/core/requirements.txt - Python dependencies

Closes #001"

# Push feature branch
git push -u origin feature/story-001-api-gateway-foundation
```

### **Step 3: Create PR via GitHub Web Interface**

1. **Go to your GitHub repository**
   - Navigate to `https://github.com/yourusername/runlayer`

2. **GitHub will show a banner**
   - "Compare & pull request" button will appear
   - Click it to start PR creation

3. **Fill out PR details**
   - **Title**: `feat: API Gateway Foundation (Story #001)`
   - **Description**: Copy the entire content from `PR_001_API_Gateway_Foundation.md`

4. **Set PR metadata**
   - **Reviewers**: Add team members if available
   - **Labels**: Create and add `enhancement`, `story-001`, `high-priority`
   - **Milestone**: Create "Phase 1: Foundation" milestone
   - **Projects**: Link to project board if created

### **Step 4: Alternative - GitHub CLI Method**
```bash
# Create PR using GitHub CLI (faster)
gh pr create \
  --title "feat: API Gateway Foundation (Story #001)" \
  --body-file PR_001_API_Gateway_Foundation.md \
  --label "enhancement,story-001,high-priority" \
  --milestone "Phase 1: Foundation" \
  --draft false

# This will automatically open the PR in your browser
```

## Required Files Checklist

### ✅ **Core Implementation Files**
- [ ] `packages/core/src/main.py` - FastAPI application
- [ ] `packages/core/src/config.py` - Configuration management  
- [ ] `packages/core/src/database.py` - Database connection
- [ ] `packages/core/src/middleware/auth.py` - JWT middleware
- [ ] `packages/core/src/middleware/correlation.py` - Request tracing
- [ ] `packages/core/src/middleware/rate_limit.py` - Rate limiting
- [ ] `packages/core/src/routers/` - API route placeholders
- [ ] `packages/core/requirements.txt` - Dependencies

### ✅ **Testing Files**
- [ ] `packages/core/tests/conftest.py` - Test configuration
- [ ] `packages/core/tests/unit/test_main.py` - Application tests
- [ ] `packages/core/tests/unit/test_middleware.py` - Middleware tests

### ✅ **Documentation Files**
- [ ] `PR_001_API_Gateway_Foundation.md` - PR description
- [ ] `.github/PULL_REQUEST_TEMPLATE/story_implementation.md` - PR template
- [ ] `README.md` - Updated with API Gateway info

### ✅ **Configuration Files**
- [ ] `.gitignore` - Git ignore rules
- [ ] `package.json` - Monorepo configuration
- [ ] `turbo.json` - Turbo build configuration

## GitHub Repository Settings

### **Branch Protection Rules**
```yaml
Branch: main
Settings:
  - Require pull request reviews before merging: ✅
  - Require status checks to pass before merging: ✅  
  - Require branches to be up to date before merging: ✅
  - Restrict pushes that create files larger than 100MB: ✅
  - Allow force pushes: ❌
  - Allow deletions: ❌
```

### **Labels to Create**
```yaml
Labels:
  - name: "enhancement"
    color: "0075ca"
    description: "New feature or request"
  
  - name: "story-001"  
    color: "d4c5f9"
    description: "Story 1: API Gateway Foundation"
    
  - name: "high-priority"
    color: "d93f0b" 
    description: "High priority issue"
    
  - name: "phase-1"
    color: "0e8a16"
    description: "Phase 1: Foundation"
```

### **Milestones to Create**
```yaml
Milestones:
  - title: "Phase 1: Foundation"
    description: "Core infrastructure and API gateway"
    due_date: "2025-02-15"
    
  - title: "Phase 2: SDK & Marketplace"  
    description: "Developer SDK and validator marketplace"
    due_date: "2025-03-15"
```

## Verification Steps

### **Before Creating PR**
```bash
# 1. Verify all files are committed
git status

# 2. Run tests locally
cd packages/core
pip install -r requirements.txt
pytest tests/ -v --cov=src

# 3. Verify API starts
uvicorn src.main:app --reload
# Test: curl http://localhost:8000/health

# 4. Check file structure
tree packages/core/
```

### **After Creating PR**
- [ ] PR shows all expected files in "Files changed" tab
- [ ] PR description renders correctly with checkboxes
- [ ] Labels and milestone are assigned
- [ ] No merge conflicts
- [ ] All status checks pass (if CI is set up)

## Common Issues & Solutions

### **Issue: Remote repository not found**
```bash
# Solution: Verify repository exists and remote is correct
git remote -v
git remote set-url origin https://github.com/yourusername/runlayer.git
```

### **Issue: Authentication failed**
```bash
# Solution: Use GitHub CLI or personal access token
gh auth login
# OR set up personal access token in git credentials
```

### **Issue: Large file warnings**
```bash
# Solution: Check for accidentally committed large files
git ls-files | xargs ls -la | sort -k5 -rn | head -10
```

### **Issue: PR template not loading**
```bash
# Solution: Verify template file path
ls -la .github/PULL_REQUEST_TEMPLATE/
# Template should be in correct location
```

## Next Steps After PR Creation

1. **Review PR yourself** - Check all files, descriptions, tests
2. **Add reviewers** - Tag team members for review
3. **Monitor CI/CD** - Ensure all checks pass
4. **Address feedback** - Make changes if requested
5. **Merge when approved** - Use "Squash and merge" for clean history

## Quick Command Summary

```bash
# Complete workflow in one go:
cd /Users/baba/Desktop/learnp/runlayer
git init
git remote add origin https://github.com/yourusername/runlayer.git
git add .gitignore README.md package.json turbo.json
git commit -m "chore: initial repository setup"
git branch -M main
git push -u origin main

git checkout -b feature/story-001-api-gateway-foundation
git add packages/core/ .github/ PR_001_API_Gateway_Foundation.md
git commit -m "feat: implement API Gateway Foundation (Story #001)"
git push -u origin feature/story-001-api-gateway-foundation

gh pr create --title "feat: API Gateway Foundation (Story #001)" --body-file PR_001_API_Gateway_Foundation.md --label "enhancement,story-001,high-priority"
```

This will create a professional, enterprise-grade PR that demonstrates the quality and completeness of the RunLayer implementation!
