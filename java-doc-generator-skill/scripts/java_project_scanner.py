#!/usr/bin/env python3
"""
java_project_scanner.py
-----------------------
Scans a Java project directory and extracts structural metadata used by the
Java Doc Agent skill to generate technical documentation.

Usage:
    python java_project_scanner.py <project-root>
    python java_project_scanner.py .

Output: JSON summary printed to stdout, one section per documentation concern.
"""

import os
import re
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EndpointInfo:
    method: str
    path: str
    controller: str
    handler: str
    params: list[str] = field(default_factory=list)


@dataclass
class ServiceInfo:
    name: str
    package: str
    public_methods: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class EntityInfo:
    name: str
    package: str
    table: Optional[str]
    fields: list[dict] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)


@dataclass
class ProjectSummary:
    project_name: str
    base_package: str
    java_version: Optional[str]
    framework_version: Optional[str]
    build_tool: str
    main_class: Optional[str]
    endpoints: list[EndpointInfo] = field(default_factory=list)
    services: list[ServiceInfo] = field(default_factory=list)
    entities: list[EntityInfo] = field(default_factory=list)
    repositories: list[str] = field(default_factory=list)
    config_classes: list[str] = field(default_factory=list)
    exception_handlers: list[str] = field(default_factory=list)
    test_classes: list[str] = field(default_factory=list)
    key_dependencies: list[str] = field(default_factory=list)
    todos: list[dict] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HTTP_METHODS = {
    "@GetMapping": "GET",
    "@PostMapping": "POST",
    "@PutMapping": "PUT",
    "@DeleteMapping": "DELETE",
    "@PatchMapping": "PATCH",
}

SPRING_ANNOTATIONS = [
    "@RestController", "@Controller", "@Service", "@Repository",
    "@Component", "@Configuration", "@Entity", "@ControllerAdvice",
]


def find_java_files(root: Path) -> list[Path]:
    return list(root.rglob("*.java"))


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def extract_class_name(content: str) -> Optional[str]:
    m = re.search(r"\bclass\s+(\w+)", content)
    return m.group(1) if m else None


def extract_package(content: str) -> Optional[str]:
    m = re.search(r"^\s*package\s+([\w.]+);", content, re.MULTILINE)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------

def scan_build_file(root: Path) -> dict:
    pom = root / "pom.xml"
    if pom.exists():
        content = read(pom)
        name = re.search(r"<artifactId>(.*?)</artifactId>", content)
        version = re.search(r"<java\.version>(.*?)</java\.version>", content)
        fw_ver = re.search(r"spring-boot[^<]*<version>(.*?)</version>", content, re.DOTALL)
        deps = re.findall(r"<artifactId>(spring-[^<]+|kafka[^<]+|redis[^<]+|jwt[^<]+|flyway[^<]+|liquibase[^<]+|swagger[^<]+|openapi[^<]+)</artifactId>", content)
        return {
            "build_tool": "Maven",
            "project_name": name.group(1) if name else root.name,
            "java_version": version.group(1) if version else None,
            "framework_version": fw_ver.group(1) if fw_ver else None,
            "key_dependencies": list(set(deps)),
        }
    gradle = root / "build.gradle"
    if gradle.exists():
        content = read(gradle)
        name_m = re.search(r"rootProject\.name\s*=\s*['\"]([^'\"]+)['\"]", content)
        java_m = re.search(r"sourceCompatibility\s*=\s*['\"]?([^'\"\s]+)", content)
        return {
            "build_tool": "Gradle",
            "project_name": name_m.group(1) if name_m else root.name,
            "java_version": java_m.group(1) if java_m else None,
            "framework_version": None,
            "key_dependencies": [],
        }
    return {"build_tool": "Unknown", "project_name": root.name}


def scan_application_config(root: Path) -> list[str]:
    """Return list of property/env-var names discovered in config files."""
    env_vars = []
    for config_file in ["application.yml", "application.yaml",
                         "application.properties", ".env.example"]:
        f = root / "src" / "main" / "resources" / config_file
        if not f.exists():
            f = root / config_file
        if f.exists():
            content = read(f)
            # properties: key=value  or  key: value
            keys = re.findall(r"^([\w.-]+)\s*[:=]", content, re.MULTILINE)
            env_vars.extend(keys[:40])  # cap at 40 to keep output manageable
    return list(dict.fromkeys(env_vars))  # deduplicate preserving order


def scan_main_class(files: list[Path]) -> Optional[str]:
    for f in files:
        content = read(f)
        if "@SpringBootApplication" in content or "public static void main" in content:
            cls = extract_class_name(content)
            if cls:
                return cls
    return None


def scan_endpoints(files: list[Path]) -> list[EndpointInfo]:
    endpoints = []
    for f in files:
        content = read(f)
        if "@RestController" not in content and "@Controller" not in content:
            continue
        controller = extract_class_name(content) or f.stem
        base_path = ""
        m = re.search(r'@RequestMapping\(["\']?(/[^)"\']*)', content)
        if m:
            base_path = m.group(1).rstrip('"').rstrip("'")

        for ann, method in HTTP_METHODS.items():
            for match in re.finditer(
                rf'{re.escape(ann)}\s*(?:\(\s*(?:value\s*=\s*)?["\']?(/[^)"\']*)?["\']?\s*\))?',
                content
            ):
                path_part = (match.group(1) or "").strip()
                full_path = base_path + path_part if path_part else base_path
                # find handler method name (next word before '(')
                rest = content[match.end():]
                handler_m = re.search(r'\b(\w+)\s*\(', rest[:300])
                handler = handler_m.group(1) if handler_m else "unknown"
                endpoints.append(EndpointInfo(
                    method=method,
                    path=full_path or "/",
                    controller=controller,
                    handler=handler,
                ))
    return endpoints


def scan_services(files: list[Path]) -> list[ServiceInfo]:
    services = []
    for f in files:
        content = read(f)
        if "@Service" not in content and "@Component" not in content:
            continue
        name = extract_class_name(content)
        pkg = extract_package(content)
        if not name:
            continue
        methods = re.findall(r'public\s+\w[\w<>, ]*\s+(\w+)\s*\(', content)
        deps = re.findall(r'@Autowired\s+(?:private\s+)?(\w+)|private final (\w+)', content)
        flat_deps = [d for pair in deps for d in pair if d and not d[0].islower()]
        services.append(ServiceInfo(
            name=name,
            package=pkg or "",
            public_methods=methods[:10],
            dependencies=list(set(flat_deps))[:8],
        ))
    return services


def scan_entities(files: list[Path]) -> list[EntityInfo]:
    entities = []
    for f in files:
        content = read(f)
        if "@Entity" not in content and "@Document" not in content:
            continue
        name = extract_class_name(content)
        pkg = extract_package(content)
        if not name:
            continue
        table_m = re.search(r'@Table\s*\(\s*name\s*=\s*"([^"]+)"', content)
        table = table_m.group(1) if table_m else None

        fields = []
        for fm in re.finditer(r'private\s+([\w<>]+)\s+(\w+)\s*;', content):
            fields.append({"type": fm.group(1), "name": fm.group(2)})

        rels = re.findall(r'@(OneToMany|ManyToOne|ManyToMany|OneToOne)\b', content)
        entities.append(EntityInfo(
            name=name,
            package=pkg or "",
            table=table,
            fields=fields[:15],
            relationships=list(set(rels)),
        ))
    return entities


def scan_repositories(files: list[Path]) -> list[str]:
    repos = []
    for f in files:
        content = read(f)
        if "@Repository" in content or "JpaRepository" in content or "CrudRepository" in content:
            name = extract_class_name(content)
            if name:
                repos.append(name)
    return repos


def scan_config_classes(files: list[Path]) -> list[str]:
    cfgs = []
    for f in files:
        content = read(f)
        if "@Configuration" in content or "SecurityFilterChain" in content:
            name = extract_class_name(content)
            if name:
                cfgs.append(name)
    return cfgs


def scan_exception_handlers(files: list[Path]) -> list[str]:
    handlers = []
    for f in files:
        content = read(f)
        if "@ControllerAdvice" in content or "@ExceptionHandler" in content:
            name = extract_class_name(content)
            if name:
                handlers.append(name)
    return handlers


def scan_test_classes(files: list[Path]) -> list[str]:
    tests = []
    for f in files:
        if "test" in str(f).lower():
            name = extract_class_name(read(f))
            if name:
                tests.append(name)
    return tests[:20]


def scan_todos(files: list[Path]) -> list[dict]:
    todos = []
    for f in files:
        content = read(f)
        for i, line in enumerate(content.splitlines(), 1):
            for marker in ("TODO", "FIXME", "HACK", "XXX"):
                if marker in line:
                    todos.append({
                        "file": f.name,
                        "line": i,
                        "text": line.strip()[:120],
                    })
                    break
    return todos[:30]


def detect_base_package(files: list[Path]) -> str:
    packages = []
    for f in files[:30]:
        pkg = extract_package(read(f))
        if pkg:
            packages.append(pkg)
    if not packages:
        return ""
    # find the shortest common prefix
    parts_list = [p.split(".") for p in packages]
    common = parts_list[0]
    for parts in parts_list[1:]:
        common = [a for a, b in zip(common, parts) if a == b]
        if not common:
            break
    return ".".join(common)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scan(root_path: str) -> ProjectSummary:
    root = Path(root_path).resolve()
    print(f"[scan] Root: {root}", file=sys.stderr)

    build_info = scan_build_file(root)
    java_files = find_java_files(root)
    print(f"[scan] Found {len(java_files)} Java files", file=sys.stderr)

    main_java = [f for f in java_files if "test" not in str(f).lower()]
    test_java = [f for f in java_files if "test" in str(f).lower()]

    return ProjectSummary(
        project_name=build_info.get("project_name", root.name),
        base_package=detect_base_package(main_java),
        java_version=build_info.get("java_version"),
        framework_version=build_info.get("framework_version"),
        build_tool=build_info.get("build_tool", "Unknown"),
        main_class=scan_main_class(main_java),
        endpoints=scan_endpoints(main_java),
        services=scan_services(main_java),
        entities=scan_entities(main_java),
        repositories=scan_repositories(main_java),
        config_classes=scan_config_classes(main_java),
        exception_handlers=scan_exception_handlers(main_java),
        test_classes=scan_test_classes(test_java),
        key_dependencies=build_info.get("key_dependencies", []),
        todos=scan_todos(main_java),
        env_vars=scan_application_config(root),
    )


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    summary = scan(root)
    print(json.dumps(asdict(summary), indent=2, default=str))
