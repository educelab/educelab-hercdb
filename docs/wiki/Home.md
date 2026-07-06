# EduceLab HercDB

A graph database (Neo4j) and REST API for Herculaneum papyrus scroll data —
PHerc fragments, their physical subdivisions (Cornice, Pezzo), imaging datasets,
and processing pipelines.

## Pages

- **[Server Setup (VM + systemd)](Server-Setup)** — stand up the REST API on a
  server as a managed service.
- **[REST API & Client Reference](REST-API-Reference)** — every endpoint and the
  matching `HercClient` method.
- **[HPC Pipeline Dry-Run Runbook](HPC-Dry-Run-Runbook)** — drive the
  acquisition-workflow submit script against HercDB from an HPC login node,
  without submitting SLURM jobs.
- **[Pipeline Recording & Cleanup](Pipeline-Recording-and-Cleanup)** — how
  submitted pipelines are recorded in the database and how an admin removes test
  records.

## The two personas this bridges

- **Papyrologists** arrive by *name* (a P.Herc. number like `421` or `118a`).
- **Computer scientists** arrive by *UUID* (an EduceLabID on a scan or pipeline).

The API resolves between the two: fetch artifacts by exact name, resolve noisy
names to candidates (`/resolve`), and bridge a UUID back to its artifact
(`/artifacts/{uuid}`).

## Authentication at a glance

Two independent secrets, on different machines:

| File | Machine | Purpose |
|------|---------|---------|
| `~/.educedb` | server (VM) | Neo4j connection credentials (TOML) |
| `~/.tokens` | server (VM) | API Bearer tokens (`name = token` per line) |
| `~/.hercdb_client.env` | client (e.g. HPC node) | `HERCDB_HOST/PORT/SCHEME/TOKEN` — token only, **no** Neo4j password |

Clients never need the Neo4j password; they hold only a Bearer token and reach
the server over HTTP.
