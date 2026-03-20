# Project Architecture

<!--
  TEMPLATE INSTRUCTIONS
  ---------------------
  Copy this file to .claude/project.architecture.md in your project root and fill
  in every placeholder marked {LIKE_THIS}. Skills read this file to know which
  build/format/test commands to run, which solution file to target, what the layer
  structure is, and which patterns are mandatory.

  Sections marked "(required)" are read directly by start-story, close-story, and
  check-story to fill in command invocations. Sections marked "(reference)" are
  contextual guidance loaded during planning — fill them in as accurately as possible
  but they do not need machine-parseable syntax.
-->

## Stack

<!--
  PRIMARY_LANGUAGE: The main programming language.
  Example: "C# (.NET 8)" | "TypeScript (Node 20)" | "Python 3.12"

  PRIMARY_FRAMEWORK: The primary application framework.
  Example: "ASP.NET Core + Blazor Server" | "Next.js 14" | "FastAPI"

  DATABASE: The database engine and ORM/query tool.
  Example: "SQL Server 2022 + Entity Framework Core 8" | "PostgreSQL + Dapper"

  UI_STACK: Frontend technology, if separate from the primary framework.
  Example: "Blazor Server + SCSS" | "React + Tailwind" | "None (API only)"
-->

- Language: {PRIMARY_LANGUAGE}
- Framework: {PRIMARY_FRAMEWORK}
- Database: {DATABASE}
- UI: {UI_STACK}

## Solution File (required)

<!--
  SOLUTION_FILE: The .sln or .slnf file passed to dotnet commands.
  Skills substitute this into build, format, and test commands.
  Example: "MyProject.sln" | "MyProject.slnf"
-->

- Solution: {SOLUTION_FILE}

## Build Commands (required)

<!--
  Skills run these commands exactly as written during Step 6 of start-story and
  close-story. Fill in the complete commands including any flags.

  FORMAT_COMMAND: The command that auto-fixes code style. Run before committing.
  Example: "dotnet format whitespace {SOLUTION_FILE}"
           "npm run lint:fix"
           "(none)" if no formatter is used

  BUILD_COMMAND: Full build command including release/prod configuration.
  Example: "dotnet build {SOLUTION_FILE} -c Release"
           "npm run build"
           "cargo build --release"

  TEST_COMMAND: Full test command. Must not rebuild (run after BUILD_COMMAND).
  Example: "dotnet test {SOLUTION_FILE} -c Release --no-build"
           "npm test"
           "cargo test"

  SCSS_COMMAND: Only needed if the project compiles SCSS to CSS.
  Example: "cd src/MyProject.Web.Shared && sass css/main.scss wwwroot/main.min.css --style=compressed --no-source-map"
  Set to "(none)" if not applicable.

  DB_BUILD_COMMAND: Only needed if the project has an SSDT database project.
  Example: "powershell -ExecutionPolicy Bypass -File tools/scripts/database/build-database.ps1"
  Set to "(none)" if not applicable.
-->

- Format: {FORMAT_COMMAND}
- Build: {BUILD_COMMAND}
- Test: {TEST_COMMAND}
- SCSS compile: {SCSS_COMMAND}
- Database build: {DB_BUILD_COMMAND}

## Layer Structure (reference)

<!--
  Describe the project's layers and their responsibilities. Skills use this during
  planning to know where new code belongs.

  Example for a Clean Architecture .NET project:
    - Domain: Entities, value objects, domain events. No external dependencies.
    - Application: Commands, queries, handlers, interfaces. Depends only on Domain.
    - Infrastructure: EF Core, external services, repositories. Implements Application interfaces.
    - Api: Thin REST layer. Dispatches MediatR commands/queries only.
    - Web: Blazor components. References only Contracts. Communicates via HTTP client.
-->

{LAYER_DESCRIPTION}

## Mandatory Patterns (reference)

<!--
  List the non-negotiable patterns enforced in this project. These are loaded during
  planning so the implementer knows what it cannot deviate from.

  Example:
    - CQRS + MediatR: All API operations use IRequest<T> / IRequestHandler<T,R>
    - Interface-first: Define interfaces in Application, implement in Infrastructure
    - Read/Write repository split: IEntityReadRepository + IEntityWriteRepository
    - FluentValidation: AbstractValidator<T> for all commands and queries
    - Async/await everywhere: Never use .Result or .Wait()
    - Guard clauses: Validate inputs early, throw ArgumentException on null/empty
-->

{MANDATORY_PATTERNS}

## Naming Conventions (reference)

<!--
  List naming rules that cause build errors if violated (e.g., IDE1006 analyzers).
  Knowing these prevents the implementer from writing code that fails the build.

  Example:
    - Private fields: _camelCase
    - Constants: PascalCase
    - Interfaces: IPascalCase
    - Type parameters: TPascalCase
    - Local variables: camelCase
-->

{NAMING_CONVENTIONS}

## Banned APIs (reference)

<!--
  List APIs that are banned by analyzer rules and what to use instead.
  Example:
    - DateTime.Now → DateTime.UtcNow (server) or BusinessClock.Now (UI)
    - Thread.Sleep → await Task.Delay()
    - SaveChanges() → SaveChangesAsync()
    - new HttpClient() → IHttpClientFactory.CreateClient()
-->

{BANNED_APIS}

## Feature Folder Layout (reference)

<!--
  Describe where new feature code goes. Example:
    Application/Features/{FeatureName}/
      Create{Entity}Command.cs   — command + handler
      Get{Entity}Query.cs        — query + handler
      Create{Entity}Validator.cs — FluentValidation validator

    Contracts/{FeatureName}/
      {Entity}Dto.cs             — request/response DTOs
      ApiRoutes.cs               — route constants (ApiRoutes.Admin.*, ApiRoutes.Dealer.*)
-->

{FEATURE_FOLDER_LAYOUT}
