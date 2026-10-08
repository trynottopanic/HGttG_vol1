# Semiotic Engine Protocol 0

Status: executable prototype contract

## What it is

Semiotic Engine Protocol 0 is the narrow local boundary between a program that
has already selected some information and a replaceable service that interprets
that information. The first service accepts text summarization jobs only.

The service is not a Node, Deck, Agent Broker, Capability Broker, personal
memory store, or application runtime. A valid Engine response is untrusted data
until its caller validates and presents it.

## Local transport

The reference service listens on `127.0.0.1` only. Requests use HTTP with a
random bearer credential written to the user's local application-data folder.
Protocol 0 makes no claim that this credential is suitable across a network.

Endpoints:

- `GET /semiotic/v0/about` — implementation and declared capabilities;
- `GET /semiotic/v0/status` — bounded queue state;
- `POST /semiotic/v0/jobs` — validate and submit one job;
- `GET /semiotic/v0/jobs/<id>` — retrieve that job's current state;
- `DELETE /semiotic/v0/jobs/<id>` — request cancellation.
- `POST /semiotic/v0/shutdown` — authenticated owner-side clean shutdown.

Except for `about`, every endpoint requires the connection credential. Responses
are UTF-8 JSON and are marked `no-store`.

Only one Engine may bind the configured address and port. Clean shutdown stops
the work queue and its managed model runtime before releasing the port.

## Request

The machine-readable definition is `semiotic_engine/schemas/request.schema.json`.
A request declares:

- protocol and caller-generated request identity;
- one supported task and its required output form;
- the complete, bounded context supplied for that task;
- provenance labels for that context;
- deadline, output, and retention limits;
- whether tools, network access, or more context may be requested.

Protocol 0 rejects tools, network access, durable retention, unknown fields,
oversized values, and unsupported media. The Engine cannot obtain context that
is absent from the request.

## Response

The machine-readable definition is `semiotic_engine/schemas/response.schema.json`.
A completed response identifies the request, state, output format, result,
uncertainty, used context identifiers, proposed actions, and timing. Protocol 0
always returns an empty proposed-actions list.

Job states are `queued`, `running`, `complete`, `failed`, or `cancelled`.
Cancellation is cooperative: a caller may request it, and the final state
records whether work stopped before producing a result.

## Prototype ceilings

- request body: 64 KiB;
- supplied text: 32,000 UTF-8 characters;
- instruction: 1,000 characters;
- requested output: at most 4,000 characters;
- accepted deadline: 1–300,000 milliseconds;
- retained job records: 16;
- active workers: one.

Completed records contain their response only in memory and expire after 15
minutes. Request text is discarded from the job record after completion.

## First proof

The deterministic reference backend finds sentences in one supplied paragraph
and returns a bounded extractive summary. It deliberately makes no claim to be
an intelligent model. Its purpose is to prove validation, isolation, queuing,
cancellation, provenance, Node relaying, and honest failure before a model
runtime is introduced.
