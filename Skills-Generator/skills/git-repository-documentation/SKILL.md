---
name: git-repository-documentation
description: Generates detailed technical design documentation from a Git repository.
license: Complete terms in LICENSE.txt
---

# Git Repository Technical Documentation Generator

## Overview

This skill analyzes a Git repository's codebase and generates comprehensive technical design documentation.  It's designed for software engineers, architects, and technical writers who need to understand or document a software project's architecture, components, and functionality.

**Keywords**: git, repository, documentation, technical design, software architecture, mermaid, diagrams

## Core Framework

### Repository Analysis
- Analyze the file structure to identify key components and modules.
- Extract code comments and inline documentation for initial understanding.
- Identify API endpoints and data models.

### Component Identification
- Group related files and functions into logical components.
- Determine the purpose and responsibility of each component.
- Identify dependencies between components.

### API Discovery
- Extract API endpoints, request parameters, and response formats.
- Document the API's functionality and usage.
- Identify data models used in the API.

### Diagram Generation
- Generate flow diagrams using Mermaid syntax to illustrate system workflows.
- Create component diagrams to visualize the system's architecture.
- Produce sequence diagrams to show interactions between components.

## Features

- Automatic extraction of code comments and documentation.
- Generation of component diagrams, flow diagrams, and sequence diagrams.
- Detailed API documentation with request/response formats.
- Comprehensive overview of the system architecture and components.

## Output Format

- The output is a markdown document containing a detailed technical design specification, including component descriptions, API documentation, diagrams, and overall system overview. The document is structured for easy readability and comprehension. Mermaid code for diagrams will be embedded directly in the markdown.

## Instructions

- Provide the URL or local path to the Git repository.
- Specify any particular components or modules to focus on, if desired.
- Indicate preferred diagram types (flow, component, sequence).

## Constraints

- The skill's effectiveness depends on the quality and completeness of the code and its comments.
- Large repositories may take significant time to process.
- The generated diagrams may require manual refinement for optimal clarity.
---