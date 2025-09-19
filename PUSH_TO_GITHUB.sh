#!/bin/bash

# GitHub Push Instructions
# ========================
#
# 1. First, create a new repository on GitHub:
#    https://github.com/new
#
# 2. Name it: ocr-document-processing (or your preferred name)
#    Do NOT initialize with README, .gitignore, or license
#
# 3. After creating, replace YOUR_USERNAME with your GitHub username below:

GITHUB_USERNAME="justintrsn"
REPO_NAME="ocr-document-processing"

echo "Setting up GitHub remote..."

# Add GitHub as origin
git remote add origin https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git

# Verify remote was added
echo "Remote added:"
git remote -v

# Push all branches
echo "Pushing to GitHub..."
git push -u origin 001-build-an-ocr

echo ""
echo "✅ Done! Your code is now on GitHub at:"
echo "   https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
echo ""
echo "To push the main branch later:"
echo "   git checkout main"
echo "   git push -u origin main"