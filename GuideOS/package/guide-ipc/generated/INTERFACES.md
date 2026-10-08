# Generated Envelope 0 interface registry

Generated from `schema/interfaces.json`; do not edit directly.

## `guide.supervisor.lifecycle` 1.2

Endpoint: `/run/guideos/supervisor/control.sock`

| Code | Operation | Grant | Retry | Descriptors |
| ---: | --- | --- | --- | --- |
| 1 | `LAUNCH` | `owner.lifecycle.control` | `none` | `none` |
| 2 | `RESOLVE` | `broker.peer.resolve` | `idempotent` | `none` |
| 3 | `STOP` | `owner.lifecycle.control` | `idempotent` | `none` |
| 4 | `STATUS` | `owner.lifecycle.control` | `idempotent` | `none` |
| 5 | `HEALTH` | `owner.lifecycle.control` | `none` | `none` |
| 6 | `FIND` | `owner.lifecycle.control` | `idempotent` | `none` |

## `guide.broker.control` 1.1

Endpoint: `/run/guideos/brokers/control.sock`

| Code | Operation | Grant | Retry | Descriptors |
| ---: | --- | --- | --- | --- |
| 1 | `SNAPSHOT` | `none` | `idempotent` | `none` |
| 2 | `RESOLVE` | `none` | `idempotent` | `none` |
| 3 | `ACQUIRE` | `installed-policy` | `none` | `none` |
| 4 | `WATCH` | `none` | `idempotent` | `none` |
| 5 | `RELEASE` | `grant-owner` | `idempotent` | `none` |
| 6 | `VALIDATE` | `grant-owner` | `idempotent` | `none` |
| 7 | `RENEW` | `grant-owner` | `idempotent` | `none` |

## `guide.broker.health` 1.0

Endpoint: `/run/guideos/brokers/health.sock`

| Code | Operation | Grant | Retry | Descriptors |
| ---: | --- | --- | --- | --- |
| 1 | `SNAPSHOT` | `system.diagnostics.read` | `none` | `none` |

## `guide.installer.control` 1.0

Endpoint: `/run/guideos/installer/control.sock`

| Code | Operation | Grant | Retry | Descriptors |
| ---: | --- | --- | --- | --- |
| 1 | `INSPECT` | `owner.installer.control` | `idempotent` | `none` |
| 2 | `BEGIN` | `owner.installer.control` | `idempotent` | `none` |
| 3 | `STATUS` | `owner.installer.control` | `idempotent` | `none` |
| 4 | `CANCEL` | `owner.installer.control` | `idempotent` | `none` |
| 5 | `INSTALLED` | `owner.installer.control` | `idempotent` | `none` |
| 6 | `UNINSTALL` | `owner.installer.control` | `idempotent` | `none` |
| 7 | `DELETE_PRIVATE_DATA` | `owner.installer.control` | `idempotent` | `none` |
| 8 | `ROLLBACK` | `owner.installer.control` | `idempotent` | `none` |
| 9 | `PREPARE_SHUTDOWN` | `owner.installer.control` | `idempotent` | `none` |

## `guide.storage.cartridges` 1.0

Endpoint: `/run/guideos-storage/cartridges.sock`

| Code | Operation | Grant | Retry | Descriptors |
| ---: | --- | --- | --- | --- |
| 1 | `LIST` | `owner.installer.control` | `idempotent` | `none` |
| 2 | `OPEN` | `owner.installer.control` | `idempotent` | `1..1 read-only-regular-archive` |

## `guide.broker.provider` 1.0

Endpoint: `/run/guideos/brokers/provider.sock`

| Code | Operation | Grant | Retry | Descriptors |
| ---: | --- | --- | --- | --- |
| 1 | `VALIDATE_PEER` | `trusted-provider` | `idempotent` | `none` |

## `guide.media.library` 1.0

Endpoint: `/run/guideos/brokers/media-library.sock`

| Code | Operation | Grant | Retry | Descriptors |
| ---: | --- | --- | --- | --- |
| 1 | `SNAPSHOT` | `media.library.browse` | `idempotent` | `none` |
| 2 | `LIST` | `media.library.browse` | `idempotent` | `none` |
| 3 | `DESCRIBE` | `media.library.browse` | `idempotent` | `none` |
| 4 | `OPEN` | `media.source.open` | `none` | `0..1 media-read` |
| 5 | `WATCH` | `media.library.browse` | `idempotent` | `none` |

| Code | Event |
| ---: | --- |
| 1 | `LIBRARY_CHANGED` |
| 2 | `SOURCE_STATE_CHANGED` |
| 3 | `RESNAPSHOT_REQUIRED` |

## `guide.media.session` 1.0

Endpoint: `/run/guideos/brokers/media-session.sock`

| Code | Operation | Grant | Retry | Descriptors |
| ---: | --- | --- | --- | --- |
| 1 | `OPEN` | `media.session.control` | `none` | `none` |
| 2 | `PLAY` | `media.session.control` | `none` | `none` |
| 3 | `PAUSE` | `media.session.control` | `none` | `none` |
| 4 | `SEEK` | `media.session.control` | `none` | `none` |
| 5 | `SELECT_AUDIO` | `media.session.control` | `none` | `none` |
| 6 | `SELECT_SUBTITLE` | `media.session.control` | `none` | `none` |
| 7 | `SET_OUTPUT` | `media.session.control` | `none` | `none` |
| 8 | `CHECKPOINT` | `media.session.control` | `none` | `none` |
| 9 | `STOP` | `media.session.control` | `idempotent` | `none` |
| 10 | `SNAPSHOT` | `media.session.control` | `idempotent` | `none` |
| 11 | `WATCH` | `media.session.control` | `idempotent` | `none` |

| Code | Event |
| ---: | --- |
| 1 | `STATE_CHANGED` |
| 2 | `POSITION_CHANGED` |
| 3 | `BUFFERING_CHANGED` |
| 4 | `TRACKS_CHANGED` |
| 5 | `SOURCE_LOST` |
| 6 | `OUTPUT_LOST` |
| 7 | `RESNAPSHOT_REQUIRED` |

## `guide.installer.parser` 1.0

Endpoint: `/run/guideos/installer/parser.sock`

| Code | Operation | Grant | Retry | Descriptors |
| ---: | --- | --- | --- | --- |
| 1 | `VERIFY` | `owner.installer.parser` | `idempotent` | `1..1 read-only-regular-archive` |
