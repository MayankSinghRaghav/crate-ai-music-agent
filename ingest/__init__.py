"""AI Review Discovery Engine.

The n8n-orchestrated insight pipeline that justified Crate: it mines public
review/forum data, clusters it into themes, and tags each theme with topic /
sentiment / unmet-need to produce a ranked opportunity backlog.

Separate from the runtime app (services/api). This slice implements the Reddit
source end-to-end; the other sources (App/Play Store, X, YouTube, Product Hunt)
plug into the same `Source` interface.
"""
