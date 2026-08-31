---
name: create-test-case
description: Create a new allocation test harness test case from a natural language scenario description
user-invocable: true
argument-hint: "<scenario description>"
---

# Create Test Case

Generate a new allocation test harness seed procedure and register it, based on a natural language scenario description.

## Arguments

The user provides a scenario description after `/create-test-case`:

Examples:
- `/create-test-case 5 real MC materials, 3 new dealers — one high seller, one medium, one brand new with zero history`
- `/create-test-case 2 synthetic materials, 10 real dealers from data.AllDealers, flat retail history`
- `/create-test-case edge case: 1 material, 1 dealer with zero retail history, high supply`

## Instructions

### Step 0: Load Project Configuration

Read `.claude/project.env.md` and `.claude/project.architecture.md` for database connection and build commands.

### Step 1: Parse the Scenario

Extract from the description:
- **Material source**: `real` (from `data.ModelHierarchy`) or `synthetic` (99xxx / 88xxx codes)
- **Material count** and optional **product line** filter (AT, MC, MS, MU, PW)
- **Dealer source**: `new` (synthetic test dealers) or `real` (from `data.AllDealers`)
- **Dealer count** and optional **sales patterns** (High, Low, Flat, Ramping)
- **Any special conditions** (zero history, high supply, aged inventory, etc.)

If anything is ambiguous, use **AskUserQuestion** to clarify before generating code.

### Step 2: Determine Next Test Case Code

Query the database or read existing seed procs to find the next available TCxx code:
```bash
sqlcmd -S "ADAM-OFFICE-CA\SQL2022" -d HondaAIM -E -Q "SELECT MAX(Code) FROM test.TestCase" -W
```
Or check existing files: `ls src/Honda.AIM.Database/Procedures/test/SeedTC*.sql`

### Step 3: Generate the Seed Procedure

Create `src/Honda.AIM.Database/Procedures/test/SeedTC{NN}_{Slug}.sql` following the pattern established by TC01 and TC02.

**Available helper procs** (use these as building blocks):

| Helper | Purpose | Key Params |
|--------|---------|------------|
| `test.GetRealMaterials` | Get real materials from `data.ModelHierarchy` + `data.MaterialMaster` | `@ProductLine`, `@Category`, `@MaxMaterials` |
| `test.GetRealDealers` | Get real active dealers from `data.AllDealers` | `@ProductLine`, `@MaxDealers` |
| `test.GenerateRetailHistory` | Generate N months of `landing.Report_Retail` rows | `@DealerNo`, `@HC_MDL_ID`, `@Pattern` ('Flat','High','Low','Ramping'), `@BaseQty` |
| `test.GenerateSupply` | Generate `landing.SupplyReport` + `landing.WishSupplyReport` | `@HC_MDL_ID`, `@TotalSupply`, `@Month1/2/3` |

**Required landing tables** the seed proc must populate:
1. `data.AllDealers` — ensure test dealers exist (for switcher lookups)
2. `landing.ModelHeirarchy` — material definitions
3. `landing.SupplyReport` — supply availability (use `test.GenerateSupply`)
4. `landing.Report_ActiveDealerList` — active dealer flags
5. `landing.Table_AllDealers` — dealer master info
6. `landing.ReportTable_AllocationDealerList` — SSA/agreement data
7. `landing.Report_Retail` — retail history (use `test.GenerateRetailHistory`)
8. `landing.Report_VinDealerInventory` — inventory VINs
9. `landing.Report_OnOrder` — open orders
10. `landing.Table_AllVins` — VIN-to-material mapping
11. `landing.Options` — per-material allocation settings
12. `landing.GlobalOptions` — 17 key-value pairs (retail windows, ranking, etc.)
13. `landing.WishSupplyReport` — Pass 2 supply (use `test.GenerateSupply`)

**Dealer number ranges by convention**:
- `99xxx` — TC01 synthetic dealers
- `88xxx` — TC02+ synthetic dealers
- Use `88{TC}{Seq}` pattern, e.g., TC03 dealers = 88301, 88302, etc.

### Step 3.5: Define Expected Outcomes

After generating the seed procedure, prompt the user for expected outcomes:

Use **AskUserQuestion**: "What outcomes do you expect from this test case? Select all that apply:"
- **High seller advantage** — a specific dealer should receive a disproportionate share (Ratio expectation)
- **Non-zero allocations** — all dealers should receive non-zero quantities (NonZero expectation)
- **Supply conservation** — total allocation per material should equal supply (Conservation expectation)
- **Custom threshold** — a specific dealer/material should meet a minimum quantity (Threshold expectation)

**Auto-suggest defaults** based on the scenario:
- If dealer patterns include "High" and "Low" → suggest Ratio expectation for the High dealer (>60%)
- If multiple dealers → suggest NonZero expectation (all dealers get allocation)
- Always suggest Conservation expectation (allocation = supply)

For each selected expectation, generate a PostDeploy patch `SeedTC{NN}Expectations.sql`:
```sql
DECLARE @TCId INT = (SELECT TestCaseId FROM test.TestCase WHERE Code = N'TC{NN}');
IF @TCId IS NOT NULL
BEGIN
    IF NOT EXISTS (SELECT 1 FROM test.TestCaseExpectation WHERE TestCaseId = @TCId AND ExpectationCode = N'EXP01')
        INSERT INTO test.TestCaseExpectation
            (TestCaseId, ExpectationCode, [Description], ExpectationType, OutputTable, TargetDealer, ExpectedValue, Tolerance)
        VALUES (@TCId, N'EXP01', N'{description}', N'{type}', N'Pass1Output', {dealer or NULL}, {value or NULL}, {tolerance or NULL});
    -- ... additional expectations ...
END
```

Add this patch file to `Script.PostDeployment.sql` and `Honda.AIM.Database.sqlproj`.

**Expectation types reference:**

| Type | Purpose | TargetDealer | ExpectedValue | Tolerance |
|------|---------|-------------|---------------|-----------|
| `Ratio` | Dealer's share of total allocation per material | Required (dealer #) | Min ratio (e.g., 0.60 = 60%) | Allowed variance (e.g., 0.05) |
| `NonZero` | All dealer/material combos have allocation > 0 | Optional (NULL = all) | NULL | NULL |
| `Conservation` | Total allocation = total supply per material | NULL | NULL | NULL |
| `Threshold` | Dealer's total allocation meets a minimum | Optional | Min quantity | Allowed variance |

### Step 4: Generate PostDeploy Registration

Create `src/Honda.AIM.Database/Scripts/PostDeploy/Patches/SeedTestCase_TC{NN}.sql`:
```sql
IF NOT EXISTS (SELECT 1 FROM test.TestCase WHERE Code = N'TC{NN}')
BEGIN
    INSERT INTO test.TestCase (Code, Name, Description, SeedProcName, [Year], [Month])
    VALUES (N'TC{NN}', N'{Name}', N'{Description}', N'test.SeedTC{NN}_{Slug}', 2026, 4);
END
```

### Step 5: Update Project Files

1. Add `<Build Include>` to `Honda.AIM.Database.sqlproj`
2. Add `<None Include>` for the PostDeploy patch
3. Add `:r` reference in `Scripts/PostDeploy/Script.PostDeployment.sql`

### Step 6: Build and Verify

1. Build DACPAC: `powershell -ExecutionPolicy Bypass -File tools/scripts/database/build-database.ps1`
2. Build solution: `dotnet build Honda.AIM.slnf -c Release`
3. Deploy SQL locally (drop + create procs via sqlcmd)
4. Register the test case via PostDeploy patch
5. Seed the test case: `EXEC test.SeedTestCase @TestCaseId = {id}, @SeededBy = 'test'`
6. Verify row counts in landing tables

### Step 7: Report

Display a summary:
```
Test Case TC{NN} created:
  Code: TC{NN}
  Name: {Name}
  Seed Proc: test.SeedTC{NN}_{Slug}
  Materials: {count} ({source})
  Dealers: {count} ({patterns})
  Expectations: {count} ({types})
  Landing rows: {total} across {datasets} datasets

Files created:
  - Procedures/test/SeedTC{NN}_{Slug}.sql
  - PostDeploy/Patches/SeedTestCase_TC{NN}.sql
  - PostDeploy/Patches/SeedTC{NN}Expectations.sql

Run with regression runner (full end-to-end):
  cd tools/Honda.AIM.Tools.RegressionRunner
  dotnet run -- --seed TC{NN}
```
