# Clean Architecture Reference — .NET

Generic rules for layered .NET solutions following Clean Architecture principles.
Enforced via NetArchTest in architecture tests.

---

## Layer Overview

```
Domain
  ^
  |
Application
  ^
  |
Infrastructure          Contracts
  ^                        ^
  |                        |
Api  <---  Web (Admin / Dealer / Portal)
```

Dependencies always point **inward**. Outer layers depend on inner layers — never the reverse.

---

## Layer Responsibilities

### Domain
- Entities, value objects, domain events, domain exceptions, Guard helpers.
- **No external dependencies.** No NuGet packages beyond base class libraries.
- Must not reference Application, Infrastructure, Contracts, or Web projects.

### Application
- Commands, queries, handlers (MediatR), validators (FluentValidation).
- Repository and service **interfaces** (`Abstractions/` subfolder).
- Business logic and orchestration only — no I/O, no EF Core, no HTTP.
- Depends only on Domain.
- Must not reference Infrastructure or Web projects.

### Contracts
- Shared DTOs, request/response objects, API route constants (`ApiRoutes`).
- May be referenced by Api, Web, and Function projects.
- Must not reference any internal project (Domain, Application, Infrastructure).
- Use `IReadOnlyList<T>` for collection properties.

### Infrastructure
- Implements Application interfaces: repositories, unit of work, external service adapters.
- EF Core `DbContext`, migrations, and query implementations live here.
- Wraps all external calls (HTTP, messaging, storage) with retry/circuit-breaker policies (Polly).
- Depends on Application and Domain. Must not reference Web projects.

### Api
- Thin REST controllers — dispatch through MediatR only.
- No business logic, no direct service calls, no direct `DbContext` injection.
- Serves multiple audiences (e.g., `/api/admin/*`, `/api/dealer/*`) from a single host.
- The single entry point for all web applications and external consumers.

### Web Projects (Admin / Dealer / Portal)
- HTTP clients of the Api — they call the API over HTTP using typed `HttpClient` services.
- Reference only the **Contracts** project (for DTOs and route constants).
- Must not reference Application, Domain, or Infrastructure.
- Must not use MediatR — MediatR is exclusively an Api-layer concern.

---

## Repository Pattern

### Interface placement
Repository interfaces belong in `Application/Abstractions/`:

```
Application/
  Abstractions/
    IUserReadRepository.cs
    IUserWriteRepository.cs
    IUnitOfWork.cs
```

### Read/Write split
Separate read and write repositories per aggregate root. Interfaces in `Application/Abstractions/`, implementations in `Infrastructure/Repositories/`.

### Unit of Work
Use `IUnitOfWork` to wrap transactional boundaries — never call `SaveChangesAsync` directly in handlers.

---

## CQRS + MediatR

- One `IRequestHandler<TRequest, TResponse>` per command or query.
- Commands mutate state; queries return data — never mix.
- Handlers live in `Application/Features/{Feature}/`:

```
Application/
  Features/
    Users/
      CreateUser/
        CreateUserCommand.cs       // IRequest<int>
        CreateUserCommandHandler.cs
        CreateUserValidator.cs     // AbstractValidator<CreateUserCommand>
      GetUser/
        GetUserQuery.cs
        GetUserQueryHandler.cs
```

- Controllers dispatch only:

```csharp
[HttpPost]
public async Task<IActionResult> Create(CreateUserRequest request, CancellationToken ct)
    => Ok(await _mediator.Send(new CreateUserCommand(request.Name), ct));
```

---

## API Routes

Centralise all route strings in `Contracts/ApiRoutes.cs` under nested static classes (e.g., `ApiRoutes.Admin`, `ApiRoutes.Dealer`). Both Api controllers and Web typed clients reference these constants — no magic strings.

---

## Dependency Injection

- Constructor injection everywhere — no service locator, no static access.
- Register Infrastructure services in `Infrastructure/DependencyInjection.cs` (`AddInfrastructure` extension).
- Register Application services in `Application/DependencyInjection.cs` (`AddApplication` extension).
- Api `Program.cs` calls both extension methods.

---

## Guarded Inputs

Validate constructor inputs with Guard helpers from Domain (`Guard.NotNull`, `Guard.NotNullOrWhiteSpace`). Use FluentValidation `AbstractValidator<T>` for command/query validation in Application. Register validators via `AddValidatorsFromAssembly`.

---

## AllowAnonymous Policy

Any controller action decorated with `[AllowAnonymous]` requires an explicit allow-list entry in `ArchitectureTests.cs`. This prevents accidental exposure of authenticated endpoints.

---

## Summary Checklist

| Rule | Layer |
|------|-------|
| No external NuGet in Domain | Domain |
| Repository interfaces in `Application/Abstractions/` | Application |
| MediatR handlers in Application, not Api | Application |
| No EF Core, HTTP, or I/O in Application | Application |
| DTOs and route constants in Contracts | Contracts |
| Contracts has no internal project references | Contracts |
| All external calls wrapped with Polly | Infrastructure |
| Controllers dispatch MediatR only | Api |
| Web projects reference only Contracts | Web |
| Web projects call Api over HTTP — no MediatR | Web |
