---
name: java-doc-agent
description: >-
  GitHub Copilot Agent skill that reads a Java project and generates
  comprehensive technical documentation. Triggers when the user asks to
  document a Java project, generate API docs, create architecture docs,
  explain Java code structure, produce a technical README, or create
  diagrams for Java classes or services. Use this skill any time a Java
  codebase, Spring Boot app, Maven/Gradle project, or Java package is
  mentioned alongside words like "document", "diagram", "explain",
  "README", "architecture", "Javadoc", "tech spec", or "onboarding".
  Also triggers on: "document my Java project", "create docs for this
  repo", "generate technical documentation", "explain the codebase".
compatibility:
  tools:
    - read_file        # GitHub Copilot file reading
    - list_dir         # directory traversal
    - search_files     # symbol / pattern search
    - get_errors       # optional – fetch build errors for context
---

# Java Technical Documentation Agent

Reads a Java project and produces professional, developer-ready
technical documentation with architecture diagrams.  Follow every
step in order.

---

## Step 1 — Discover the Project Layout

Use `list_dir` (or equivalent) starting from the workspace root.
Collect and note:

1. **Build system** — `pom.xml` (Maven) or `build.gradle` / `build.gradle.kts` (Gradle)
2. **Entry points** — classes with `public static void main`, `@SpringBootApplication`, `@QuarkusMain`, etc.
3. **Package structure** — top-level packages under `src/main/java`
4. **Test layout** — `src/test/java` (note frameworks: JUnit 4/5, Mockito, Testcontainers)
5. **Config files** — `application.properties`, `application.yml`, `Dockerfile`, `docker-compose.yml`
6. **Key folders** — `controller`, `service`, `repository`, `model`/`entity`, `config`, `dto`, `util`, `exception`

> Read the full directory tree first; resist jumping to individual files until Step 2.

---

## Step 2 — Extract Core Metadata

Read the build file and gather:

| Field | Where to find it |
|---|---|
| Project name | `<artifactId>` / `rootProject.name` |
| Version | `<version>` / `version =` |
| Java version | `<java.version>` / `sourceCompatibility` |
| Key dependencies | `<dependencies>` / `dependencies {}` block |
| Main framework | Spring Boot, Quarkus, Micronaut, plain Java, etc. |

Then read `src/main/resources/application.properties` or `application.yml`
for: server port, active profiles, database URL pattern, external service
URLs, feature flags.

---

## Step 3 — Analyse the Source Code

Work through source files in this priority order.  Use `search_files`
for patterns rather than reading every file individually.

### 3a. Entry Point & Bootstrap
- Read the `main` class (or `@SpringBootApplication` class).
- Note component scan base packages, imported auto-configurations, and beans registered manually.

### 3b. API Surface (REST / GraphQL / gRPC)
Search for:
```
@RestController   @Controller   @RequestMapping
@GetMapping  @PostMapping  @PutMapping  @DeleteMapping  @PatchMapping
@GrpcService   @QueryMapping   @MutationMapping
```
For each endpoint collect: HTTP method, path, request body type, response type, auth annotation.

### 3c. Domain / Business Layer
Search for `@Service`, `@Component`, `@UseCase` (if clean arch).
For each service: note public methods, which repositories or external
services they call, and key business rules / validations.

### 3d. Data Layer
Search for `@Repository`, `extends JpaRepository`, `extends CrudRepository`,
`@Mapper` (MyBatis).
Note: entity names, database (from config), custom query methods.

### 3e. Domain Models
Search for `@Entity`, `@Table`, `record`, `@Document` (Mongo).
Collect: class names, key fields, relationships (`@OneToMany`, etc.).

### 3f. Security & Cross-Cutting
Search for `@SecurityConfiguration`, `WebSecurityConfigurerAdapter`,
`SecurityFilterChain`, `@Aspect`, `@Around`, `@Scheduled`.

### 3g. Exception Handling
Search for `@ControllerAdvice`, `@ExceptionHandler`, custom exception classes.

---

## Step 4 — Build the Documentation

Produce a single Markdown document following the structure below.
Load [doc-template.md](./templates/doc-template.md) for section details.

```
# <Project Name> — Technical Documentation

## 1. Overview
## 2. Technology Stack
## 3. Project Structure
## 4. Architecture
   ### 4a. High-Level Diagram   ← Mermaid graph LR
   ### 4b. Component Interactions ← Mermaid sequenceDiagram
## 5. API Reference
## 6. Data Model
   ### Entity Relationship      ← Mermaid erDiagram
## 7. Class Diagram             ← Mermaid classDiagram (key classes only)
## 8. Configuration & Environment Variables
## 9. Running Locally
## 10. Testing
## 11. Key Design Decisions & Patterns
## 12. Known Limitations / TODOs
```

---

## Step 5 — Diagrams

Follow [diagram-rules.md](./references/diagram-rules.md) strictly.

### Required diagrams

| Diagram | Type | When |
|---|---|---|
| High-level architecture | `graph LR` | Always |
| Request lifecycle | `sequenceDiagram` | If REST/gRPC endpoints exist |
| Entity relationships | `erDiagram` | If JPA entities exist |
| Class diagram | `classDiagram` | If complex class hierarchies exist |
| Data flow | `flowchart LR` | If event-driven / messaging present |

Always wrap in fenced code blocks:
````
```mermaid
graph LR
  ...
```
````

Label every arrow with a short verb: `calls`, `returns`, `reads`, `writes`,
`publishes`, `consumes`, `authenticates`.

---

## Step 6 — Output Format

**Preferred**: Write to `docs/TECHNICAL_DOCUMENTATION.md` in the workspace.
**Fallback**: Return the full Markdown in the chat response.

The file must be self-contained — no broken internal links, all diagrams
embedded inline.

---

## Hard Rules

- **Never invent** methods, classes, or endpoints — only document what exists.
- **Never expose secrets** — replace actual values from config with `<YOUR_VALUE>`.
- **Always use Mermaid**, never PlantUML or graphviz.
- If a section has no content (e.g., no entities) — **omit** that section.
- For large projects (>50 classes), focus the class diagram on the **public API boundary** — controllers, services, key domain objects.
- If the code has TODO/FIXME comments, surface them in section 12.
- If `get_errors` is available, call it and note any build errors in section 12.
