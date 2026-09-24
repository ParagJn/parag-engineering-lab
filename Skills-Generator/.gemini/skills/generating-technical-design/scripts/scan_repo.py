#!/usr/bin/env python3
"""
scan_repo.py

Recursively scans a repository file hierarchy, detects languages and frameworks,
parses package manifests, and generates a structured JSON summary for architecture analysis.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

IGNORE_DIRS: Set[str] = {
    ".git",
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    ".turbo",
    ".cache",
    "coverage",
}

EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".py": "Python",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".sql": "SQL",
    ".proto": "Protobuf",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
}

MANIFEST_FILES: Dict[str, str] = {
    "package.json": "Node.js (npm/yarn/pnpm)",
    "pyproject.toml": "Python (Poetry/PEP 621)",
    "requirements.txt": "Python (pip)",
    "Pipfile": "Python (Pipenv)",
    "setup.py": "Python (setuptools)",
    "go.mod": "Go Modules",
    "Cargo.toml": "Rust (Cargo)",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)",
    "build.gradle.kts": "Kotlin (Gradle)",
    "Gemfile": "Ruby (Bundler)",
    "composer.json": "PHP (Composer)",
    "docker-compose.yml": "Docker Compose",
    "docker-compose.yaml": "Docker Compose",
    "Dockerfile": "Docker",
}


def parse_package_json(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
            dependencies = list(data.get("dependencies", {}).keys())
            dev_dependencies = list(data.get("devDependencies", {}).keys())
            scripts = data.get("scripts", {})
            return {
                "name": data.get("name", "unknown"),
                "version": data.get("version", "unknown"),
                "dependencies": dependencies,
                "dev_dependencies": dev_dependencies,
                "scripts": list(scripts.keys()),
            }
    except Exception as e:
        return {"error": f"Failed to parse package.json: {str(e)}"}


def parse_pyproject_toml(path: Path) -> Dict[str, Any]:
    dependencies: List[str] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            capture = False
            for line in lines:
                line_str = line.strip()
                if line_str.startswith("[tool.poetry.dependencies]") or line_str.startswith("[project.dependencies]"):
                    capture = True
                    continue
                elif line_str.startswith("[") and capture:
                    capture = False
                if capture and line_str and not line_str.startswith("#"):
                    pkg_name = line_str.split("=")[0].split(">")[0].split("<")[0].strip().strip('"').strip("'")
                    if pkg_name:
                        dependencies.append(pkg_name)
        return {"dependencies": dependencies}
    except Exception as e:
        return {"error": f"Failed to parse pyproject.toml: {str(e)}"}


def parse_go_mod(path: Path) -> Dict[str, Any]:
    modules: List[str] = []
    module_name = "unknown"
    go_version = "unknown"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            in_require = False
            for line in f:
                line_str = line.strip()
                if line_str.startswith("module "):
                    module_name = line_str.replace("module ", "").strip()
                elif line_str.startswith("go "):
                    go_version = line_str.replace("go ", "").strip()
                elif line_str.startswith("require ("):
                    in_require = True
                    continue
                elif line_str == ")" and in_require:
                    in_require = False
                elif in_require and line_str:
                    parts = line_str.split()
                    if parts:
                        modules.append(parts[0])
                elif line_str.startswith("require ") and not in_require:
                    parts = line_str.replace("require ", "").strip().split()
                    if parts:
                        modules.append(parts[0])
        return {
            "module": module_name,
            "go_version": go_version,
            "dependencies": modules,
        }
    except Exception as e:
        return {"error": f"Failed to parse go.mod: {str(e)}"}


def scan_directory(root_path: Path, max_depth: int = 6) -> Dict[str, Any]:
    file_counts: Dict[str, int] = {}
    language_counts: Dict[str, int] = {}
    found_manifests: Dict[str, str] = {}
    parsed_manifest_details: Dict[str, Any] = {}
    entry_points: List[str] = []
    directory_tree: List[str] = []

    root_path = root_path.resolve()

    if not root_path.exists():
        sys.stderr.write(f"Error: Path '{root_path}' does not exist.\n")
        sys.exit(1)

    if not root_path.is_dir():
        sys.stderr.write(f"Error: Path '{root_path}' is not a directory.\n")
        sys.exit(1)

    common_entry_filenames = {
        "main.go",
        "index.ts",
        "index.js",
        "server.ts",
        "server.js",
        "app.ts",
        "app.js",
        "main.py",
        "app.py",
        "wsgi.py",
        "asgi.py",
        "manage.py",
        "main.rs",
        "Application.java",
        "config.ru",
    }

    for current_root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]

        rel_path = Path(current_root).relative_to(root_path)
        depth = len(rel_path.parts)

        if depth > max_depth:
            dirs.clear()
            continue

        if rel_path != Path("."):
            directory_tree.append(str(rel_path))

        for file_name in files:
            file_path = Path(current_root) / file_name
            rel_file_path = file_path.relative_to(root_path)

            ext = file_path.suffix.lower()
            file_counts[ext] = file_counts.get(ext, 0) + 1

            if ext in EXTENSION_LANGUAGE_MAP:
                lang = EXTENSION_LANGUAGE_MAP[ext]
                language_counts[lang] = language_counts.get(lang, 0) + 1

            if file_name in MANIFEST_FILES:
                found_manifests[str(rel_file_path)] = MANIFEST_FILES[file_name]
                if file_name == "package.json" and len(rel_file_path.parts) <= 3:
                    parsed_manifest_details[str(rel_file_path)] = parse_package_json(file_path)
                elif file_name == "pyproject.toml" and len(rel_file_path.parts) <= 3:
                    parsed_manifest_details[str(rel_file_path)] = parse_pyproject_toml(file_path)
                elif file_name == "go.mod" and len(rel_file_path.parts) <= 3:
                    parsed_manifest_details[str(rel_file_path)] = parse_go_mod(file_path)

            if file_name in common_entry_filenames or any(file_name.endswith(e) for e in [".entry.ts", ".server.ts"]):
                entry_points.append(str(rel_file_path))

    return {
        "root_directory": str(root_path),
        "detected_manifests": found_manifests,
        "manifest_details": parsed_manifest_details,
        "languages": language_counts,
        "file_extensions": file_counts,
        "detected_entry_points": sorted(entry_points),
        "directory_topology": sorted(directory_tree)[:80],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan a git repository to extract dependencies, entry points, and architectural topology."
    )
    parser.add_argument("repo_path", nargs="?", default=".", help="Path to the repository root (default: current directory)")
    parser.add_argument("--output", "-o", help="Optional output JSON file path (default: stdout)")
    parser.add_argument("--max-depth", type=int, default=5, help="Maximum directory depth to scan (default: 5)")

    args = parser.parse_args()

    repo_dir = Path(args.repo_path)
    result = scan_directory(repo_dir, max_depth=args.max_depth)

    json_output = json.dumps(result, indent=2)

    if args.output:
        out_path = Path(args.output)
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"Successfully wrote scan summary to {out_path}")
        except Exception as e:
            sys.stderr.write(f"Error writing output to {out_path}: {str(e)}\n")
            sys.exit(1)
    else:
        print(json_output)


if __name__ == "__main__":
    main()
