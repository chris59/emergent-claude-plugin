# .NET Coding Conventions Reference

Generic coding standards for .NET C# projects. All rules below are enforced as build
errors via `TreatWarningsAsErrors`, Roslyn analyzers, and `.editorconfig`.

---

## C# Naming (IDE1006 — Build Errors)

| Scope | Style | Example |
|-------|-------|---------|
| Constants | PascalCase | `const int MaxRetries = 3;` |
| Static readonly (public / protected / internal) | PascalCase | `static readonly TimeSpan DefaultTimeout = ...;` |
| Private / internal fields | `_camelCase` | `private int _count;` |
| Interfaces | `I` + PascalCase | `IUserService` |
| Type parameters | `T` + PascalCase | `TResult`, `TEntity` |
| Classes, structs, enums | PascalCase | `AllocationRun` |
| Methods, properties, events | PascalCase | `GetUsers()`, `IsActive` |
| Parameters | camelCase | `void Process(int dealerId)` |
| Local variables and local functions | camelCase | `var result = ...; bool isValid(x) => ...` |

**Special cases:**
- Primary constructor parameters → camelCase (they are parameters, not properties).
- Record positional parameters → PascalCase (they become auto-properties).
- Local `const` → camelCase (it is a local variable by scoping rules).

---

## Banned APIs (RS0030 — Build Errors)

Banned via `Microsoft.CodeAnalysis.BannedApiAnalyzers`. Test projects are excluded from the ban.

| Banned | Use Instead | Reason |
|--------|-------------|--------|
| `DateTime.Now` | `DateTime.UtcNow` (server) or timezone-aware clock service (UI) | Timezone-ambiguous in cloud/multi-region deployments |
| `Thread.Sleep(int)` | `await Task.Delay(int)` | Blocks a thread-pool thread |
| `DbContext.SaveChanges()` / `SaveChanges(bool)` | `await SaveChangesAsync()` | Blocks request thread; forces sync-over-async |
| `new HttpClient()` | `IHttpClientFactory.CreateClient()` | Socket exhaustion under load |

### DateTime context rules

| Context | Use |
|---------|-----|
| Database timestamps, audit fields, server-side calculations | `DateTime.UtcNow` |
| UI display defaults, "saved at" labels, modal date defaults | Timezone-aware clock service (e.g., `BusinessClock.Now`) |

Capture the clock value once before LINQ queries to avoid repeated conversions:

```csharp
var now = BusinessClock.Now;
var current = items.Where(x => x.Month == now.Month && x.Year == now.Year);
```

---

## Code Style Rules

Enforced via `.editorconfig` + `TreatWarningsAsErrors`.

### File-scoped namespaces
```csharp
// Correct
namespace MyApp.Features.Users;

// Wrong — do not use block-scoped namespaces
namespace MyApp.Features.Users
{
    ...
}
```

### Braces — always required, Allman style
```csharp
// Correct
if (isValid)
{
    Process();
}

// Wrong — braceless single-line
if (isValid)
    Process();
```

### var usage
```csharp
// Explicit type for built-in types
int count = 0;
string name = "Alice";

// var when type is apparent from the right-hand side
var user = new User("Alice");
var users = await _repository.ListAsync(ct);
```

### Additional style rules
- No `this.` prefix on member access.
- Use predefined aliases: `int` not `Int32`, `string` not `String`.

---

## Async / Await

- All I/O-bound methods must be `async Task` or `async Task<T>`.
- Never use `.Result` or `.Wait()` — they cause deadlocks in ASP.NET contexts.
- Pass `CancellationToken` through the full call chain.
- Suffix async method names with `Async`: `GetUserAsync`, `SaveChangesAsync`.

---

## Code Quality

### Zero-warning build
`TreatWarningsAsErrors` is enabled for all non-test projects. Every compiler warning is a build failure.

### Roslyn analyzers
Projects reference built-in CA rules, Meziantou.Analyzer, and Roslynator. Together they enforce 700+ code quality rules covering null safety, performance, API usage, and style.

### Formatting gate
The CI pipeline runs:

```bash
dotnet format <solution>.sln whitespace --verify-no-changes
```

PRs with formatting drift are blocked. Fix locally before pushing:

```bash
dotnet format <solution>.sln
```

---

## NuGet Package Management

**Central Package Management** — all package versions live in `Directory.Packages.props` at the repo root.

```xml
<!-- Directory.Packages.props -->
<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
  </PropertyGroup>
  <ItemGroup>
    <PackageVersion Include="Dapper" Version="2.1.35" />
  </ItemGroup>
</Project>
```

In `.csproj` files, **never** include a `Version` attribute:

```xml
<!-- Correct -->
<PackageReference Include="Dapper" />

<!-- Wrong — version belongs in Directory.Packages.props -->
<PackageReference Include="Dapper" Version="2.1.35" />
```

---

## Guard Clauses

Validate constructor inputs with `Guard.NotNull` / `Guard.NotNullOrWhiteSpace` from Domain.
Validate command/query inputs with FluentValidation `AbstractValidator<T>` in Application.

---

## Collection Types

- Use `IReadOnlyList<T>` for returned collections from repositories and queries.
- Use `IEnumerable<T>` only when lazy evaluation is genuinely needed.
- Never return mutable `List<T>` from public APIs.

---

## File Header Comments (Required)

All new files must include a four-line header:

```csharp
// Purpose: Brief description of what this file does.
// Layer: Domain | Application (CQRS Command/Query) | Infrastructure | Presentation
// Collaborators: Key interfaces or services this class depends on.
// Notes: Any constraints, idempotency guarantees, retry behavior, etc.
```
