# Project Environment

<!--
  TEMPLATE INSTRUCTIONS
  ---------------------
  Copy this file to .claude/project.env.md in your project root and fill in every
  placeholder marked {LIKE_THIS}. Skills read this file to construct ADO API URLs,
  database connection strings, branch names, and environment-specific commands.

  Do NOT commit secrets (passwords, PATs) here — use environment variables or a
  gitignored appsettings.local.json for those values. This file is safe to commit
  as long as it contains only structural config (org names, resource group names,
  server names, auth methods).
-->

## Azure DevOps

<!--
  ADO_ORG: The ADO organization slug — the segment after dev.azure.com/ in your board URL.
  Example: "DKYInc" from https://dev.azure.com/DKYInc/

  ADO_ORG_URL: The full organization URL used in `az devops configure`.
  Example: "https://dev.azure.com/DKYInc"

  ADO_PROJECT_NAME: The ADO project name EXACTLY as it appears in the URL (space-sensitive).
  Example: "Honda AIM"  (note: has a space, not a dot)

  ADO_REPO_ID: The GUID of the git repository — used in PR REST API calls.
  To find it: az repos show --repository "Your Repo Name" --query id -o tsv
  Example: "8fafb937-1bcd-474d-837b-da3daeddfc44"

  ADO_RESOURCE_ID: The Azure resource ID for ADO token acquisition.
  This is almost always "499b84ac-1321-427f-aa17-267ca6975798" (the ADO app ID).
  Only change this if your org uses a custom AAD app registration for ADO access.
-->

- Organization: {ADO_ORG_URL}
- Project: {ADO_PROJECT_NAME}
- Repository ID: {ADO_REPO_ID}
- ADO Resource ID: {ADO_RESOURCE_ID}

## Database

<!--
  DB_SERVER: SQL Server instance name (local) or FQDN (Azure SQL).
  Local example:  "MYPC\SQL2022"
  Azure example:  "sql-myproject-dev.database.windows.net"

  DB_NAME: The database name.
  Example: "MyProjectDb"

  DB_AUTH_METHOD: How sqlcmd authenticates.
  Options: "Windows Authentication (-E)" | "SQL Login (-U/-P)" | "Azure AD (-G)"

  DB_LOCAL_CONNECT: Full sqlcmd connection string for local dev.
  Example: "-S \"MYPC\\SQL2022\" -d MyProjectDb -E"
-->

- Server: {DB_SERVER}
- Database: {DB_NAME}
- Auth: {DB_AUTH_METHOD}
- Local sqlcmd flags: {DB_LOCAL_CONNECT}

## Azure

<!--
  AZURE_TENANT_ID: The AAD tenant GUID. Used in `az login --tenant` and token acquisition.
  Example: "f37eec50-a8de-4a3e-b5c1-123456789abc"

  AZURE_SUBSCRIPTION: Subscription name or GUID for resource operations.
  Example: "Honda AIM Dev" or "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

  AZURE_RESOURCE_GROUP: Resource group that contains the project's Azure resources.
  Example: "rg-honda-aim-dev"
-->

- Tenant ID: {AZURE_TENANT_ID}
- Subscription: {AZURE_SUBSCRIPTION}
- Resource Group: {AZURE_RESOURCE_GROUP}

## Branch Naming

<!--
  BRANCH_USERNAME: The personal identifier segment used in feature branch names.
  This matches whoever the primary developer is on this machine.
  Example: "chrisa"  → branches look like feature/chrisa/1234-my-story

  BASE_BRANCH: The integration branch that feature branches target.
  Example: "develop" or "main"
-->

- Pattern: feature/{BRANCH_USERNAME}/{storyId}-{slug}
- Username: {BRANCH_USERNAME}
- Base branch: {BASE_BRANCH}

## Remote Environments

<!--
  Connection strings for DEV, UAT, and PROD SQL databases.
  Used by the DatabaseSeeder tool and manual sqlcmd deployments.

  IMPORTANT: Do NOT put passwords here. Store them in:
    - appsettings.local.json (gitignored) for tool config
    - Environment variables (SQLCMDPASSWORD, etc.) for sqlcmd
    - Key Vault references for deployed environments

  Format: "Server=...;Database=...;User ID=...;TrustServerCertificate=True"
  Set to "N/A" if the environment does not exist for this project.
-->

- DEV: {DEV_CONNECTION_STRING}
- UAT: {UAT_CONNECTION_STRING}
- PROD: {PROD_CONNECTION_STRING}
