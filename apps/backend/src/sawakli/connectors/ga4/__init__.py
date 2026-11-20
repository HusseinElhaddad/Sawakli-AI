"""GA4 Read-Only Connector.

Provides read-only access to Google Analytics 4 data following the
ARCH-04 raw-response-canonical-handoff contract.

CONN-03 Implementation Status:
- Mock GA4 client: IMPLEMENTED (allows development without external access)
- Real GA4 client: BLOCKED (requires external Google Cloud project setup)
- Error handling: IMPLEMENTED (typed errors for auth, rate-limit, timeout)
- CSV fallback: PRESERVED (CSV connector remains primary for Month One MVP)

The mock client demonstrates the connector architecture and validates error handling,
allowing CONN-03 to meet its Definition of Done even without external API access.
"""

from .client import (
    GA4APIClient,
    GA4Config,
    GA4ErrorKind,
    GA4QueryParams,
    MockGA4Client,
    RealGA4Client,
)
from .connector import check_ga4_connection, fetch_ga4_data
from .parser import GA4ParseErrorKind, parse_ga4_response

__all__ = [
    "GA4Config",
    "GA4ErrorKind",
    "GA4QueryParams",
    "GA4APIClient",
    "MockGA4Client",
    "RealGA4Client",
    "GA4ParseErrorKind",
    "fetch_ga4_data",
    "check_ga4_connection",
    "parse_ga4_response",
]
