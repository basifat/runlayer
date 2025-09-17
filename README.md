# RunLayer - The Trust Layer for AI

> Validate AI outputs with cryptographic proof. Share, remix, and verify AI correctness.

[![Build Status](https://github.com/runlayer/runlayer/workflows/CI/badge.svg)](https://github.com/runlayer/runlayer/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🚀 Vision

RunLayer is the **trust layer for AI** - a platform that validates AI outputs through pluggable validators, stores cryptographic proof, and produces shareable RunProofs. Think "DocuSign for AI correctness" + "Grammarly-style suggestions" + "GitHub remixability."

### Core Innovation
- **RunProof™**: Cryptographically signed proof artifacts with public sharing
- **Validator System**: Pluggable validation with BYOV (Bring Your Own Validator)
- **Viral Sharing**: One-click remix and attribution chains
- **Enterprise Ready**: Compliance packs (MiFID II, HIPAA, GDPR)

## 📦 Monorepo Structure

```
runlayer/
├── packages/
│   ├── core/                 # Core API and business logic (FastAPI)
│   ├── web/                  # Next.js web application
│   ├── chrome-extension/     # Chrome extension (Manifest V3)
│   ├── sdk-python/          # Python SDK for validators
│   ├── sdk-typescript/      # TypeScript SDK for validators
│   ├── cli/                 # CLI tools for developers
│   └── shared/              # Shared types and utilities
├── infrastructure/          # Terraform/AWS infrastructure
├── docs/                   # Documentation
└── tools/                  # Development and build tools
```

## 🛠 Tech Stack

### Backend
- **API**: FastAPI (Python 3.11+) on AWS Lambda
- **Database**: PostgreSQL with row-level security (multi-tenant)
- **Queue**: Temporal for durable validator execution
- **Storage**: S3 + CloudFront CDN
- **Cache**: Redis (ElastiCache)

### Frontend
- **Web**: Next.js 14+ with TypeScript
- **Extension**: Chrome Manifest V3
- **Mobile**: React Native (future)

### Infrastructure
- **Cloud**: AWS (serverless-first)
- **Orchestration**: Serverless Framework
- **Monitoring**: DataDog + AWS CloudWatch
- **Security**: WASM validators, cryptographic proofs

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- Docker
- AWS CLI configured

### Development Setup

```bash
# Clone the repository
git clone https://github.com/runlayer/runlayer.git
cd runlayer

# Install dependencies
npm install

# Start development environment
npm run dev
```

This will start:
- Core API on http://localhost:8000
- Web app on http://localhost:3000
- Chrome extension in development mode

### Environment Variables

Copy `.env.example` to `.env.local` and configure:

```bash
# Database
DATABASE_URL="postgresql://user:pass@localhost:5432/runlayer"

# AWS
AWS_REGION="us-east-1"
AWS_ACCESS_KEY_ID="your-key"
AWS_SECRET_ACCESS_KEY="your-secret"

# Redis
REDIS_URL="redis://localhost:6379"

# Temporal
TEMPORAL_HOST="localhost:7233"
```

## 📋 Development Workflow

### Story Implementation Process

Each user story follows this workflow:

1. **Branch**: `feature/story-{number}-{description}`
2. **Implementation**: Follow acceptance criteria
3. **Testing**: Unit + integration tests
4. **PR**: Use provided template
5. **Review**: Automated checks + manual review
6. **Deploy**: Automatic deployment on merge

### PR Template

```markdown
## Story Implementation

**Story**: #[number] - [title]
**Type**: feature | bugfix | refactor | docs

### Implementation
- [ ] All acceptance criteria met
- [ ] Tests added/updated (>80% coverage)
- [ ] Documentation updated
- [ ] Performance benchmarks included
- [ ] Security review completed

### Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] E2E tests pass (if applicable)
- [ ] Manual testing completed

### Performance
- [ ] API response time: < 300ms p99
- [ ] Database queries optimized
- [ ] Memory usage acceptable
- [ ] No performance regressions

### Security
- [ ] Input validation implemented
- [ ] SQL injection prevention
- [ ] XSS protection
- [ ] Authentication/authorization correct
```

## 🎯 Roadmap

### Phase 1: Foundation (Month 1-2)
- [x] Repository structure
- [ ] Core API infrastructure
- [ ] Chrome extension MVP
- [ ] Public proof pages
- [ ] Basic marketplace

### Phase 2: Growth (Month 2-3)
- [ ] BYOV SDK (Python/TypeScript)
- [ ] MCP server integration
- [ ] Advanced marketplace
- [ ] Community features

### Phase 3: Enterprise (Month 3-4)
- [ ] RBAC and compliance
- [ ] Advanced analytics
- [ ] Enterprise integrations
- [ ] On-premises deployment

### Phase 4: Scale (Month 4+)
- [ ] Cryptographic proofs
- [ ] Certification pipeline
- [ ] Advanced ecosystem
- [ ] Global deployment

## 📊 Success Metrics

### Growth Targets
- **Month 1**: 10K users (Chrome extension launch)
- **Month 2**: 100K users (viral proof sharing)
- **Month 3**: 500K users (marketplace network effects)
- **Month 4**: 1M users (enterprise adoption)

### Technical KPIs
- **API Performance**: p99 < 300ms
- **Uptime**: 99.9%
- **Viral Coefficient**: >1.0 by Month 3
- **Proof Sharing**: 50% of proofs shared publicly

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](./CONTRIBUTING.md) for details.

### Development Commands

```bash
# Install dependencies
npm install

# Run all packages in development
npm run dev

# Build all packages
npm run build

# Run tests
npm run test

# Lint and format
npm run lint
npm run format

# Type checking
npm run type-check
```

## 📄 License

MIT License - see [LICENSE](./LICENSE) file for details.

## 🔗 Links

- [Documentation](https://docs.runlayer.com)
- [API Reference](https://api.runlayer.com/docs)
- [Chrome Extension](https://chrome.google.com/webstore/detail/runlayer)
- [Community Forum](https://community.runlayer.com)
- [Status Page](https://status.runlayer.com)

---

**RunLayer** - Making AI trustworthy, one validation at a time. 🛡️✨
