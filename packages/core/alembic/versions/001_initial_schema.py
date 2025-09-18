"""Initial schema for Story 2: Multi-Tenant Database Setup (Senior Developer Approach)

Revision ID: 001
Revises: 
Create Date: 2025-09-17 12:45:00

Senior developer approach:
- Simple tenant filtering (YAGNI - no complex RLS initially)
- Optimized indexes for performance requirements
- Clean schema following established patterns
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables with optimized indexes."""
    
    # Create workspaces table
    op.create_table('workspaces',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('owner_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('max_validators', sa.Integer(), nullable=False),
        sa.Column('max_executions_per_day', sa.Integer(), nullable=False),
        sa.Column('max_storage_mb', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_workspace_owner_type', 'workspaces', ['owner_id', 'type'])
    
    # Create validator_registry table
    op.create_table('validator_registry',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('code_bundle_url', sa.String(length=500), nullable=False),
        sa.Column('wasm_hash', sa.String(length=64), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_validator_lookup', 'validator_registry', ['workspace_id', 'name', 'version', 'is_active'])
    op.create_index('idx_validator_workspace_active', 'validator_registry', ['workspace_id', 'is_active'])
    
    # Create proof_lake table
    op.create_table('proof_lake',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('validator_id', sa.String(), nullable=False),
        sa.Column('input_hash', sa.String(length=64), nullable=False),
        sa.Column('output_hash', sa.String(length=64), nullable=False),
        sa.Column('proof_data', sa.JSON(), nullable=False),
        sa.Column('execution_time_ms', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('synced_to_cloud', sa.Boolean(), nullable=False),
        sa.Column('sync_timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['validator_id'], ['validator_registry.id'], ),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_proof_workspace_created', 'proof_lake', ['workspace_id', 'created_at'])
    op.create_index('idx_proof_sync_pending', 'proof_lake', ['workspace_id', 'synced_to_cloud'])
    
    # Create replay_jobs table
    op.create_table('replay_jobs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('validator_ids', sa.JSON(), nullable=False),
        sa.Column('input_criteria', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('total_validations', sa.Integer(), nullable=False),
        sa.Column('completed_validations', sa.Integer(), nullable=False),
        sa.Column('failed_validations', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_replay_workspace_status', 'replay_jobs', ['workspace_id', 'status'])
    op.create_index('idx_replay_created', 'replay_jobs', ['created_at'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('replay_jobs')
    op.drop_table('proof_lake')
    op.drop_table('validator_registry')
    op.drop_table('workspaces')
