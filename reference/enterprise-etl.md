# Enterprise ETL Patterns Reference

Generic patterns for reliable, idempotent, auditable file-based ETL pipelines in .NET.

---

## File Naming Conventions

Consistent, parseable file names enable automated discovery and chronological ordering.

### Recommended format
```
{TransactionCode}_{Descriptor}_{Target}_{Timestamp}.{ext}
```

Examples:
```
SAP_InventorySnapshot_Dealers_20260115T143022Z.dat
FTP_DealerOrders_Western_20260115T143022Z.txt
```

| Segment | Purpose |
|---------|---------|
| `TransactionCode` | Identifies the source system or message type (e.g., `SAP`, `MFT`) |
| `Descriptor` | Human-readable dataset name (e.g., `InventorySnapshot`, `DealerOrders`) |
| `Target` | Scope or audience (e.g., region, business unit, `All`) |
| `Timestamp` | ISO 8601 UTC — `yyyyMMdd'T'HHmmss'Z'` — enables sort-by-name = sort-by-age |

### Extension requirement
Automated discovery requires a known extension. Use `.dat` or `.txt` for text-based files.
Files without a recognised extension must be skipped (not failed) during directory scanning.

---

## Idempotency

Every pipeline run must be safe to re-execute against the same source file without
producing duplicate or corrupted data.

### Hash-based deduplication
Compute a SHA-256 hash of the file content before processing:

```csharp
using var stream = File.OpenRead(filePath);
var hash = Convert.ToHexString(await SHA256.HashDataAsync(stream));
```

Store the hash in a processing log table (`etl.FileProcessingLog`) with columns `FileName`, `ContentHash` (CHAR(64)), `Status` (Pending/Success/Failed/Skipped), and `ErrorMessage`. Add unique constraints on both `ContentHash` and `FileName`.

On re-run: if the hash already exists with `Status = 'Success'`, skip and log "Skipped (duplicate)". If the same filename arrives with a different hash, treat it as a replacement and process it after archiving the original.

---

## Archive Before Process

**Always copy the file to durable storage before processing begins.**

Rationale: if processing fails mid-way, the source file may have been deleted or
overwritten by the time you retry. The archive is the permanent record.

```csharp
// 1. Download from source (SFTP, FTP, blob trigger, etc.)
var localPath = await _downloader.DownloadAsync(remoteFile);

// 2. Archive to cloud storage immediately
await _archiveStorage.UploadAsync(
    containerName: "etl-archive",
    blobName: $"{DateTime.UtcNow:yyyy/MM/dd}/{Path.GetFileName(localPath)}",
    sourcePath: localPath);

// 3. Process from the local copy
await _processor.ProcessAsync(localPath);

// 4. Clean up local temp file
File.Delete(localPath);
```

Archive naming convention: prefix with `yyyy/MM/dd/` to organise blobs by date.

---

## Chronological Processing

When multiple files are waiting in the source directory, process them **oldest first**
(ascending by timestamp in filename or file system modified date).

```csharp
var files = Directory
    .EnumerateFiles(sourceDirectory, "*.dat")
    .OrderBy(f => File.GetLastWriteTimeUtc(f));
```

Processing in the wrong order can cause later snapshots to be overwritten by earlier
data, making the final state incorrect.

---

## Per-File Processing (Not Batch Directory)

Process **one file per pipeline invocation**, not an entire directory in a single
transaction. Benefits:

- Failures are isolated — one bad file does not block others.
- Progress is granular — the log shows exactly which file failed.
- Retry is targeted — only the failed file is reprocessed.

Use a queue (Azure Service Bus, Storage Queue) or a database cursor table to claim and dispatch one file at a time.

---

## Pattern-Based File Validation

Before processing, validate that the file matches an expected pattern. Skip — do not
fail — files that are not recognised:

```csharp
private static readonly Regex ExpectedPattern =
    new(@"^SAP_[A-Za-z]+_[A-Za-z]+_\d{8}T\d{6}Z\.dat$", RegexOptions.Compiled);

if (!ExpectedPattern.IsMatch(Path.GetFileName(filePath)))
{
    _logger.LogWarning("Skipping unrecognised file: {File}", filePath);
    return ProcessResult.Skipped;
}
```

Log all skipped files. Investigate accumulation of skipped files — it indicates a
naming convention drift in the upstream system.

---

## File Lifecycle

```
Source (SFTP / FTP / Blob trigger)
    |
    | 1. Download to local temp
    v
Local Temp File
    |
    | 2. Archive to cloud storage
    v
Archive (Azure Blob — permanent)
    |
    | 3. Hash check — already processed?
    |       Yes → log "Skipped" → done
    |       No  → continue
    v
Staging (database or in-memory)
    |
    | 4. Validate + transform
    v
Target (database, API, downstream system)
    |
    | 5. Mark Success in processing log
    v
    | 6. Delete local temp file
    v
Done
```

### Cleanup policy
- **Local temp files**: delete immediately after archive upload succeeds.
- **Source files on SFTP/FTP**: delete or move to a `processed/` subfolder after the
  full pipeline succeeds. Never delete before archive upload.
- **Archive blobs**: retain indefinitely (or per data retention policy). Never delete
  archive blobs as part of normal ETL operation.

---

## Error Handling and Retry

| Failure point | Strategy |
|--------------|---------|
| Download fails | Retry with exponential backoff (Polly). Leave file on source. |
| Archive upload fails | Retry. Do not proceed to processing. |
| Validation fails | Mark `Status = 'Failed'`, log error, move to next file. |
| Processing fails mid-way | Rollback transaction. Mark `Status = 'Failed'`. Retry is safe because processing is idempotent. |
| Downstream write fails | Retry. If permanent, mark failed and alert. |

Use Polly for all external I/O (SFTP, blob, HTTP) — `WaitAndRetryAsync` with exponential backoff, plus a circuit breaker for sustained failures.

---

## Observability

Every file processed must produce a structured log entry with: `event`, `fileName`, `contentHash`, `rowsInserted`, `rowsUpdated`, `rowsSkipped`, `durationMs`, `status`.

Alert on:
- Processing lag > threshold (files sitting in `Pending` state longer than expected).
- `Failed` status rate exceeding 5% of files in a rolling window.
- Skipped files accumulating without investigation.
