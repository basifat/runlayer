#!/usr/bin/env python3
"""
Automated PR Generator for RunLayer Stories

This script automatically creates GitHub PRs from story implementations,
following the established PR template and naming conventions.
"""

import os
import json
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import yaml
import re

class AutoPRGenerator:
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.stories_config = self.repo_root / "stories-config.yml"
        self.pr_template = self.repo_root / ".github" / "PULL_REQUEST_TEMPLATE" / "story_implementation.md"
        
    def load_story_config(self, story_id: str) -> Dict:
        """Load story configuration from YAML file."""
        if not self.stories_config.exists():
            raise FileNotFoundError(f"Stories config not found: {self.stories_config}")
            
        with open(self.stories_config, 'r') as f:
            config = yaml.safe_load(f)
            
        story_key = f"story_{story_id.zfill(3)}"
        if story_key not in config['stories']:
            raise ValueError(f"Story {story_id} not found in config")
            
        return config['stories'][story_key]
    
    def generate_branch_name(self, story: Dict) -> str:
        """Generate branch name from story info."""
        story_num = story['id'].zfill(3)
        title_slug = re.sub(r'[^a-zA-Z0-9]+', '-', story['title'].lower()).strip('-')
        return f"feature/story-{story_num}-{title_slug}"
    
    def generate_commit_message(self, story: Dict) -> str:
        """Generate detailed commit message."""
        story_type = story.get('type', 'feat')
        story_num = story['id'].zfill(3)
        
        message = f"{story_type}: {story['title']} (Story #{story['id']})\n\n"
        
        # Add implementation summary
        if 'implementation_summary' in story:
            message += f"{story['implementation_summary']}\n\n"
        
        # Add key features
        if 'key_features' in story:
            message += "Key Features:\n"
            for feature in story['key_features']:
                message += f"- {feature}\n"
            message += "\n"
        
        # Add performance notes
        if 'performance' in story:
            message += "Performance:\n"
            for perf in story['performance']:
                message += f"- {perf}\n"
            message += "\n"
        
        # Add security notes
        if 'security' in story:
            message += "Security:\n"
            for sec in story['security']:
                message += f"- {sec}\n"
            message += "\n"
        
        # Add files
        if 'files_added' in story:
            message += "Files Added:\n"
            for file in story['files_added']:
                message += f"- {file}\n"
            message += "\n"
        
        message += f"Closes #{story['id']}"
        return message
    
    def generate_pr_description(self, story: Dict) -> str:
        """Generate PR description from story and template."""
        with open(self.pr_template, 'r') as f:
            template = f.read()
        
        # Replace template variables
        replacements = {
            '[number]': story['id'],
            '[title]': story['title'],
            '[Link to story in backlog]': story.get('backlog_link', 'TBD'),
        }
        
        description = template
        for placeholder, value in replacements.items():
            description = description.replace(placeholder, str(value))
        
        return description
    
    def create_feature_branch(self, branch_name: str) -> bool:
        """Create and switch to feature branch."""
        try:
            # Check if branch already exists
            result = subprocess.run(['git', 'branch', '--list', branch_name], 
                                  capture_output=True, text=True, cwd=self.repo_root)
            
            if branch_name in result.stdout:
                print(f"Branch {branch_name} already exists, switching to it")
                subprocess.run(['git', 'checkout', branch_name], cwd=self.repo_root, check=True)
            else:
                print(f"Creating new branch: {branch_name}")
                subprocess.run(['git', 'checkout', '-b', branch_name], cwd=self.repo_root, check=True)
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error creating branch: {e}")
            return False
    
    def commit_story_files(self, story: Dict, commit_message: str) -> bool:
        """Add and commit story implementation files."""
        try:
            # Add files specified in story config
            if 'files_to_commit' in story:
                for file_pattern in story['files_to_commit']:
                    subprocess.run(['git', 'add', file_pattern], cwd=self.repo_root, check=True)
            else:
                # Add all changes if no specific files specified
                subprocess.run(['git', 'add', '.'], cwd=self.repo_root, check=True)
            
            # Check if there are changes to commit
            result = subprocess.run(['git', 'diff', '--cached', '--quiet'], 
                                  cwd=self.repo_root, capture_output=True)
            
            if result.returncode == 0:
                print("No changes to commit")
                return False
            
            # Commit changes
            subprocess.run(['git', 'commit', '-m', commit_message], cwd=self.repo_root, check=True)
            print("Changes committed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error committing files: {e}")
            return False
    
    def push_branch(self, branch_name: str) -> bool:
        """Push branch to origin."""
        try:
            subprocess.run(['git', 'push', '-u', 'origin', branch_name], 
                          cwd=self.repo_root, check=True)
            print(f"Branch {branch_name} pushed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error pushing branch: {e}")
            return False
    
    def create_github_pr(self, story: Dict, branch_name: str, pr_description: str) -> bool:
        """Create GitHub PR using GitHub CLI."""
        try:
            story_num = story['id'].zfill(3)
            pr_title = f"{story.get('type', 'feat')}: {story['title']} (Story #{story['id']})"
            
            # Create temporary file for PR description
            pr_desc_file = self.repo_root / f"temp_pr_desc_{story_num}.md"
            with open(pr_desc_file, 'w') as f:
                f.write(pr_description)
            
            # Create PR using GitHub CLI
            cmd = [
                'gh', 'pr', 'create',
                '--title', pr_title,
                '--body-file', str(pr_desc_file),
                '--label', f"enhancement,story-{story_num},high-priority",
            ]
            
            # Add milestone if specified
            if 'milestone' in story:
                cmd.extend(['--milestone', story['milestone']])
            
            # Add assignees if specified
            if 'assignees' in story:
                cmd.extend(['--assignee', ','.join(story['assignees'])])
            
            subprocess.run(cmd, cwd=self.repo_root, check=True)
            
            # Clean up temp file
            pr_desc_file.unlink()
            
            print(f"PR created successfully for Story #{story['id']}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error creating PR: {e}")
            return False
    
    def generate_pr_for_story(self, story_id: str, auto_commit: bool = False) -> bool:
        """Generate complete PR for a story."""
        try:
            print(f"\n🚀 Generating PR for Story #{story_id}")
            
            # Load story configuration
            story = self.load_story_config(story_id)
            print(f"📋 Story: {story['title']}")
            
            # Generate branch name and commit message
            branch_name = self.generate_branch_name(story)
            commit_message = self.generate_commit_message(story)
            pr_description = self.generate_pr_description(story)
            
            print(f"🌿 Branch: {branch_name}")
            
            # Create feature branch
            if not self.create_feature_branch(branch_name):
                return False
            
            # Commit files (if auto_commit is True)
            if auto_commit:
                if not self.commit_story_files(story, commit_message):
                    print("⚠️  No changes to commit, but continuing with PR creation")
            else:
                print("📝 Manual commit required. Run:")
                print(f"   git add <files>")
                print(f"   git commit -m \"{commit_message.split(chr(10))[0]}\"")
                
                response = input("Continue with PR creation? (y/n): ")
                if response.lower() != 'y':
                    return False
            
            # Push branch
            if not self.push_branch(branch_name):
                return False
            
            # Create GitHub PR
            if not self.create_github_pr(story, branch_name, pr_description):
                return False
            
            print(f"✅ PR created successfully for Story #{story_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error generating PR: {e}")
            return False
    
    def batch_generate_prs(self, story_ids: List[str], auto_commit: bool = False) -> Dict[str, bool]:
        """Generate PRs for multiple stories."""
        results = {}
        
        for story_id in story_ids:
            results[story_id] = self.generate_pr_for_story(story_id, auto_commit)
            
        return results

def main():
    parser = argparse.ArgumentParser(description='Automated PR Generator for RunLayer Stories')
    parser.add_argument('story_ids', nargs='+', help='Story IDs to generate PRs for')
    parser.add_argument('--repo-root', default='.', help='Repository root directory')
    parser.add_argument('--auto-commit', action='store_true', 
                       help='Automatically commit changes (use with caution)')
    parser.add_argument('--batch', action='store_true', 
                       help='Process multiple stories in batch')
    
    args = parser.parse_args()
    
    generator = AutoPRGenerator(args.repo_root)
    
    if args.batch:
        results = generator.batch_generate_prs(args.story_ids, args.auto_commit)
        
        print("\n📊 Batch Results:")
        for story_id, success in results.items():
            status = "✅ Success" if success else "❌ Failed"
            print(f"  Story #{story_id}: {status}")
    else:
        for story_id in args.story_ids:
            generator.generate_pr_for_story(story_id, args.auto_commit)

if __name__ == '__main__':
    main()
