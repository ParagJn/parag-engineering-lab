---
name: anthropic-tutorial-and-github-library-search
description: Finds high-quality Anthropic tutorials and relevant GitHub libraries, then organizes them into a practical research summary.
license: Complete terms in LICENSE.txt
---

# Anthropic Tutorial & GitHub Library Search

## Overview

This skill helps users quickly discover useful Anthropic tutorials, official documentation, community guides, and GitHub libraries related to the Anthropic API and Claude ecosystem. It is designed for developers, researchers, and technical learners who want curated, actionable resources instead of raw search results.

**Keywords**: Anthropic, Claude, tutorials, GitHub, libraries, SDKs, API, developer resources, web research, code examples

## Core Framework

### Search Scope
- Search for official Anthropic documentation, quickstarts, cookbooks, and tutorials
- Search for GitHub repositories related to Anthropic integrations, SDKs, wrappers, and example apps
- Include both official and reputable community-created resources

### Source Prioritization
- Prioritize official Anthropic sources first
- Prioritize active GitHub repositories with clear documentation and recent maintenance
- Prefer high-signal technical blogs, documentation pages, and example repos over low-quality SEO pages

### Resource Evaluation
- Check whether the tutorial is beginner-friendly, intermediate, or advanced
- Note the primary language or framework used, such as Python, TypeScript, Node.js, or LangChain
- Assess repository usefulness based on stars, activity, README quality, examples, and relevance

### Result Organization
- Separate findings into Tutorials, Official Resources, and GitHub Libraries
- Summarize each resource in 1-2 lines
- Highlight best picks for common use cases like getting started, building chat apps, tool use, and API integration

## Features

- Curates official Anthropic tutorials and docs
- Finds relevant GitHub libraries and example repositories
- Filters for quality, relevance, and practical usefulness
- Organizes results by category and experience level
- Highlights recommended starting points
- Summarizes why each resource matters

## Output Format

- A categorized resource list with sections for:
  - Official Anthropic Resources
  - Tutorials and Guides
  - GitHub Libraries and Repositories
- Each item should include:
  - Title
  - Link
  - Source type
  - Short summary
  - Recommended audience or use case
- End with a brief “Best Starting Resources” section

## Instructions

- Search the web for Anthropic tutorials, official docs, and GitHub libraries
- Prefer official Anthropic sources when available
- Include a balanced mix of tutorials and code repositories
- Summarize each result clearly and concisely
- Identify the language, framework, or platform when possible
- Flag especially useful beginner resources and production-ready libraries
- Organize results into readable sections with direct links

## Constraints

- Do not include irrelevant AI resources that are not meaningfully related to Anthropic
- Avoid low-quality, duplicate, or clearly outdated sources when better alternatives exist
- Do not invent repository details, maintenance status, or documentation quality
- Keep summaries short, factual, and useful
- Focus on practical developer value over generic search listings