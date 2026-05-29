"""Terminal API adapters for the local SNInsightTerminal server.

The project still uses the existing ThreadingHTTPServer entrypoint.  This
package only provides stable schemas, JSON sanitising helpers, and a small
route adapter for the new /api/terminal/* endpoints.
"""

